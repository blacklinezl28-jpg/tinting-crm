from datetime import datetime, timezone, timedelta, time as d_time
import io
import json
import pandas as pd
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import psycopg2
import psycopg2.extras

app = FastAPI(title="Detailing & Tinting CRM Pro")

# Налаштування шаблонів (папка templates)
templates = Jinja2Templates(directory="templates")

KYIV_TZ = timezone(timedelta(hours=3))

def get_now_kyiv():
    return datetime.now(KYIV_TZ)

# Підключення до Supabase
def init_connection():
    try:
        # Тут ви будете використовувати ваші st.secrets або змінні середовища (os.environ)
        import os
        return psycopg2.connect(
            host=os.getenv("PG_HOST", "ваш_хост_supabase"),
            database=os.getenv("PG_DATABASE", "postgres"),
            user=os.getenv("PG_USER", "postgres"),
            password=os.getenv("PG_PASSWORD", "ваш_пароль"),
            port=os.getenv("PG_PORT", "5432"),
            sslmode="require"
        )
    except Exception as e:
        print(f"Помилка підключення до БД: {e}")
        return None

def run_query(query, params=(), fetch=True):
    conn = init_connection()
    if conn is None:
        return pd.DataFrame()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            if fetch:
                try:
                    data = cur.fetchall()
                    return pd.DataFrame(data)
                except psycopg2.ProgrammingError:
                    return pd.DataFrame()
            else:
                conn.commit()
    except Exception as e:
        if conn:
            try: conn.rollback() 
            except: pass
        print(f"Помилка бази даних: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_saved_film_meters(car_model):
    if not car_model:
        return 3.0
    res = run_query("SELECT avg_meters FROM film_usage WHERE LOWER(car_model) = LOWER(%s)", (car_model.strip(),))
    if not res.empty:
        return float(res.iloc[0]["avg_meters"])
    return 3.0

def save_film_meters(car_model, meters):
    if not car_model:
        return
    run_query("""
        INSERT INTO film_usage (car_model, avg_meters) 
        VALUES (%s, %s)
        ON CONFLICT (car_model) 
        DO UPDATE SET avg_meters = EXCLUDED.avg_meters;
    """, (car_model.strip(), meters), fetch=False)

# --- МАРШРУТИ (ROUTES) ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Головна сторінка (Інформаційна панель)
    month_str = get_now_kyiv().strftime("%Y-%m")
    
    month_df = run_query(
        "SELECT SUM(final_price) as earned, SUM(net_profit) as profit, COUNT(*) as cars_count FROM appointments WHERE status = 'Виконано' AND date LIKE %s",
        (f"{month_str}%",)
    )
    month_spoiled_df = run_query(
        "SELECT SUM(s.cost_uah) as total_spoiled_cost FROM appointment_spoiled s JOIN appointments a ON s.appointment_id = a.id WHERE a.date LIKE %s",
        (f"{month_str}%",)
    )
    spoiled_month_cost = month_spoiled_df["total_spoiled_cost"].iloc[0] if not month_spoiled_df.empty and pd.notna(month_spoiled_df["total_spoiled_cost"].iloc[0]) else 0.0
    
    total_queue_df = run_query("SELECT COUNT(*) as total_queue FROM appointments WHERE status = 'Очікує'")
    total_queue_count = total_queue_df["total_queue"].iloc[0] if not total_queue_df.empty and pd.notna(total_queue_df["total_queue"].iloc[0]) else 0

    earned_month = month_df["earned"].iloc[0] if not month_df.empty and pd.notna(month_df["earned"].iloc[0]) else 0.0
    raw_profit_month = month_df["profit"].iloc[0] if not month_df.empty and pd.notna(month_df["profit"].iloc[0]) else 0.0
    profit_month = raw_profit_month - spoiled_month_cost
    cars_month_count = month_df["cars_count"].iloc[0] if not month_df.empty and pd.notna(month_df["cars_count"].iloc[0]) else 0

    next_app = run_query("SELECT * FROM appointments WHERE status = 'Очікує' ORDER BY date ASC, time ASC LIMIT 1")
    next_appointment = next_app.to_dict(orient="records")[0] if not next_app.empty else None

    cal_apps = run_query("SELECT date, status, car_brand, car_model, car_number, time FROM appointments ORDER BY date ASC, time ASC")
    calendar_data = cal_apps.to_dict(orient="records") if not cal_apps.empty else []

    low_stock = run_query("SELECT item_name, meters_left, min_limit, unit FROM inventory WHERE meters_left <= min_limit")
    low_stock_alerts = low_stock.to_dict(orient="records") if not low_stock.empty else []

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "earned_month": int(earned_month),
        "profit_month": int(profit_month),
        "spoiled_month_cost": int(spoiled_month_cost),
        "cars_month_count": int(cars_month_count),
        "total_queue_count": int(total_queue_count),
        "next_appointment": next_appointment,
        "calendar_data": calendar_data,
        "low_stock_alerts": low_stock_alerts
    })

@app.get("/appointments", response_class=HTMLResponse)
async def appointments_page(request: Request):
    apps = run_query("SELECT * FROM appointments WHERE status != 'Виконано' AND status != 'Скасовано' ORDER BY date ASC, time ASC")
    services = run_query("SELECT * FROM services")
    inventory = run_query("SELECT * FROM inventory")
    
    return templates.TemplateResponse("appointments.html", {
        "request": request,
        "appointments": apps.to_dict(orient="records") if not apps.empty else [],
        "services": services.to_dict(orient="records") if not services.empty else [],
        "inventory": inventory.to_dict(orient="records") if not inventory.empty else []
    })

@app.post("/appointments/add")
async def add_appointment(
    client_name: str = Form(...),
    client_phone: str = Form(...),
    car_brand: str = Form(...),
    car_model: str = Form(...),
    car_number: str = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    comment: str = Form("")
):
    created_at_str = get_now_kyiv().strftime("%Y-%m-%d %H:%M:%S")
    res_id = run_query(
        """INSERT INTO appointments (client_name, client_phone, car_brand, car_model, car_number, 
                                     created_at, date, time, status, final_price, material_cost, net_profit, comment) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Очікує', 0, 0, 0, %s) RETURNING id""",
        (client_name, client_phone, car_brand, car_model, car_number, created_at_str, date, time, comment)
    )
    return RedirectResponse(url="/appointments", status_code=303)

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    inv = run_query("SELECT * FROM inventory")
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "inventory": inv.to_dict(orient="records") if not inv.empty else []
    })

@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    rep = run_query("SELECT * FROM appointments ORDER BY id DESC")
    return templates.TemplateResponse("reports.html", {
        "request": request,
        "appointments": rep.to_dict(orient="records") if not rep.empty else []
    })
