from datetime import datetime, timezone, timedelta
import os
import io
import json
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import psycopg2
import psycopg2.extras

app = FastAPI(title="Detailing & Tinting CRM Pro")

templates = Jinja2Templates(directory="templates")

KYIV_TZ = timezone(timedelta(hours=3))

def get_now_kyiv():
    return datetime.now(KYIV_TZ)

def init_connection():
    try:
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
        return [] if fetch else None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            if fetch:
                data = cur.fetchall()
                return [{str(k): v for k, v in dict(row).items()} for row in data]
            else:
                conn.commit()
    except Exception as e:
        if conn:
            try: conn.rollback() 
            except: pass
        print(f"Помилка бази даних: {e}")
        return [] if fetch else None
    finally:
        if conn:
            conn.close()

def get_saved_film_meters(car_model):
    if not car_model:
        return 3.0
    res = run_query("SELECT avg_meters FROM film_usage WHERE LOWER(car_model) = LOWER(%s)", (car_model.strip(),))
    if res:
        return float(res[0]["avg_meters"])
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
    month_str = get_now_kyiv().strftime("%Y-%m")
    
    month_res = run_query(
        "SELECT SUM(final_price) as earned, SUM(net_profit) as profit, COUNT(*) as cars_count FROM appointments WHERE status = 'Виконано' AND date LIKE %s",
        (f"{month_str}%",)
    )
    month_spoiled_res = run_query(
        "SELECT SUM(s.cost_uah) as total_spoiled_cost FROM appointment_spoiled s JOIN appointments a ON s.appointment_id = a.id WHERE a.date LIKE %s",
        (f"{month_str}%",)
    )
    
    spoiled_month_cost = month_spoiled_res[0]["total_spoiled_cost"] if month_spoiled_res and month_spoiled_res[0]["total_spoiled_cost"] is not None else 0.0
    total_queue_res = run_query("SELECT COUNT(*) as total_queue FROM appointments WHERE status = 'Очікує'")
    total_queue_count = total_queue_res[0]["total_queue"] if total_queue_res and total_queue_res[0]["total_queue"] is not None else 0

    earned_month = month_res[0]["earned"] if month_res and month_res[0]["earned"] is not None else 0.0
    raw_profit_month = month_res[0]["profit"] if month_res and month_res[0]["profit"] is not None else 0.0
    profit_month = raw_profit_month - spoiled_month_cost
    cars_month_count = month_res[0]["cars_count"] if month_res and month_res[0]["cars_count"] is not None else 0

    next_app = run_query("SELECT * FROM appointments WHERE status = 'Очікує' ORDER BY date ASC, time ASC LIMIT 1")
    next_appointment = next_app[0] if next_app else None
    calendar_data = run_query("SELECT date, status, car_brand, car_model, car_number, time FROM appointments ORDER BY date ASC, time ASC")
    low_stock_alerts = run_query("SELECT item_name, meters_left, min_limit, unit FROM inventory WHERE meters_left <= min_limit")

    context = {
        "request": request,
        "earned_month": int(earned_month),
        "profit_month": int(profit_month),
        "spoiled_month_cost": int(spoiled_month_cost),
        "cars_month_count": int(cars_month_count),
        "total_queue_count": int(total_queue_count),
        "next_appointment": next_appointment,
        "calendar_data": calendar_data,
        "low_stock_alerts": low_stock_alerts
    }
    return templates.TemplateResponse(request, "dashboard.html", context)

@app.get("/appointments", response_class=HTMLResponse)
async def appointments_page(request: Request):
    apps = run_query("SELECT * FROM appointments WHERE status != 'Виконано' AND status != 'Скасовано' ORDER BY date ASC, time ASC")
    services = run_query("SELECT * FROM services")
    inventory = run_query("SELECT * FROM inventory")
    
    context = {
        "request": request,
        "appointments": apps,
        "services": services,
        "inventory": inventory
    }
    return templates.TemplateResponse(request, "appointments.html", context)

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
    run_query(
        """INSERT INTO appointments (client_name, client_phone, car_brand, car_model, car_number, 
                                     created_at, date, time, status, final_price, material_cost, net_profit, comment) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Очікує', 0, 0, 0, %s)""",
        (client_name, client_phone, car_brand, car_model, car_number, created_at_str, date, time, comment),
        fetch=False
    )
    return RedirectResponse(url="/appointments", status_code=303)

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    inv = run_query("SELECT * FROM inventory")
    context = {
        "request": request,
        "inventory": inv
    }
    return templates.TemplateResponse(request, "inventory.html", context)

@app.post("/inventory/add")
async def add_inventory(
    item_name: str = Form(...),
    category: str = Form(...),
    width_cm: float = Form(0.0),
    meters_left: float = Form(...),
    min_limit: float = Form(5.0),
    price_usd: float = Form(...),
    exchange_rate: float = Form(41.0),
    unit: str = Form("м")
):
    cost_uah = price_usd * exchange_rate
    run_query(
        """INSERT INTO inventory (item_name, category, width_cm, meters_left, min_limit, price_usd, exchange_rate, cost_per_unit_uah, unit) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (item_name, category, width_cm, meters_left, min_limit, price_usd, exchange_rate, cost_uah, unit),
        fetch=False
    )
    return RedirectResponse(url="/inventory", status_code=303)

@app.get("/services", response_class=HTMLResponse)
async def services_page(request: Request):
    serv = run_query("SELECT * FROM services")
    context = {"request": request, "services": serv}
    return templates.TemplateResponse(request, "services.html", context)

@app.post("/services/add")
async def add_service(service_name: str = Form(...), default_price: float = Form(...)):
    run_query("INSERT INTO services (service_name, default_price) VALUES (%s, %s)", (service_name, default_price), fetch=False)
    return RedirectResponse(url="/services", status_code=303)

@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    rep = run_query("SELECT * FROM appointments ORDER BY id DESC")
    debts = run_query("SELECT * FROM appointments WHERE payment_type = 'Борг' AND status = 'Виконано'")
    context = {
        "request": request,
        "appointments": rep,
        "debts": debts
    }
    return templates.TemplateResponse(request, "reports.html", context)

@app.get("/backup/export")
async def export_backup():
    tables = [
        "services", "inventory", "appointments", "appointment_photos",
        "appointment_services", "appointment_inventory", "inventory_log",
        "appointment_spoiled", "film_usage"
    ]
    backup_data = {}
    for t in tables:
        df_t = run_query(f"SELECT * FROM {t}")
        backup_data[t] = df_t if df_t else []
    
    json_bytes = json.dumps(backup_data, ensure_ascii=False, indent=4, default=str).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(json_bytes),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=crm_backup_{get_now_kyiv().strftime('%Y-%m-%d')}.json"}
    )
