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

# --- МАРШРУТИ ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, month: str = None):
    current_month_str = get_now_kyiv().strftime("%Y-%m")
    selected_month = month if month else current_month_str
    
    month_res = run_query(
        "SELECT SUM(final_price) as earned, SUM(net_profit) as profit, COUNT(*) as cars_count FROM appointments WHERE status = 'Виконано' AND date LIKE %s",
        (f"{selected_month}%",)
    )
    total_booked_res = run_query(
        "SELECT COUNT(*) as total_booked FROM appointments WHERE date LIKE %s",
        (f"{selected_month}%",)
    )
    month_spoiled_res = run_query(
        "SELECT SUM(s.cost_uah) as total_spoiled_cost FROM appointment_spoiled s JOIN appointments a ON s.appointment_id = a.id WHERE a.date LIKE %s",
        (f"{selected_month}%",)
    )
    
    spoiled_month_cost = month_spoiled_res[0]["total_spoiled_cost"] if month_spoiled_res and month_spoiled_res[0]["total_spoiled_cost"] is not None else 0.0
    earned_month = month_res[0]["earned"] if month_res and month_res[0]["earned"] is not None else 0.0
    raw_profit_month = month_res[0]["profit"] if month_res and month_res[0]["profit"] is not None else 0.0
    profit_month = raw_profit_month - spoiled_month_cost
    cars_done_count = month_res[0]["cars_count"] if month_res and month_res[0]["cars_count"] is not None else 0
    cars_booked_count = total_booked_res[0]["total_booked"] if total_booked_res and total_booked_res[0]["total_booked"] is not None else 0

    next_app = run_query("SELECT * FROM appointments WHERE status = 'Очікує' ORDER BY date ASC, time ASC LIMIT 1")
    next_appointment = next_app[0] if next_app else None

    calendar_data = run_query(
        "SELECT * FROM appointments WHERE date LIKE %s ORDER BY date ASC, time ASC",
        (f"{selected_month}%",)
    )
    low_stock_alerts = run_query("SELECT item_name, meters_left, min_limit, unit FROM inventory WHERE meters_left <= min_limit")

    context = {
        "request": request,
        "selected_month": selected_month,
        "earned_month": int(earned_month),
        "profit_month": int(profit_month),
        "spoiled_month_cost": int(spoiled_month_cost),
        "cars_done_count": int(cars_done_count),
        "cars_booked_count": int(cars_booked_count),
        "next_appointment": next_appointment,
        "calendar_data": calendar_data,
        "low_stock_alerts": low_stock_alerts
    }
    return templates.TemplateResponse(request, "dashboard.html", context)

@app.get("/appointments", response_class=HTMLResponse)
async def appointments_page(request: Request):
    # Виводимо активні записи або всі (тут показуємо не виконані/не скасовані для швидкої роботи, а загальна база буде в Звітах/Клієнтах)
    apps = run_query("SELECT * FROM appointments ORDER BY date DESC, time DESC")
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
    comment: str = Form(""),
    status: str = Form("Очікує"),
    final_price: float = Form(0.0)
):
    created_at_str = get_now_kyiv().strftime("%Y-%m-%d %H:%M:%S")
    run_query(
        """INSERT INTO appointments (client_name, client_phone, car_brand, car_model, car_number, 
                                     created_at, date, time, status, final_price, material_cost, net_profit, comment) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s)""",
        (client_name, client_phone, car_brand, car_model, car_number, created_at_str, date, time, status, final_price, final_price, comment),
        fetch=False
    )
    return RedirectResponse(url="/appointments", status_code=303)

@app.post("/appointments/update_status/{app_id}")
async def update_appointment_status(app_id: int, status: str = Form(...)):
    run_query("UPDATE appointments SET status = %s WHERE id = %s", (status, app_id), fetch=False)
    return RedirectResponse(url="/appointments", status_code=303)

@app.get("/services", response_class=HTMLResponse)
async def services_page(request: Request):
    serv = run_query("SELECT * FROM services ORDER BY id DESC")
    context = {"request": request, "services": serv}
    return templates.TemplateResponse(request, "services.html", context)

@app.post("/services/add")
async def add_service(service_name: str = Form(...), default_price: float = Form(...)):
    run_query("INSERT INTO services (service_name, default_price) VALUES (%s, %s)", (service_name, default_price), fetch=False)
    return RedirectResponse(url="/services", status_code=303)

@app.post("/services/delete/{service_id}")
async def delete_service(service_id: int):
    run_query("DELETE FROM services WHERE id = %s", (service_id,), fetch=False)
    return RedirectResponse(url="/services", status_code=303)

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    inv = run_query("SELECT * FROM inventory")
    context = {"request": request, "inventory": inv}
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

@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    rep = run_query("SELECT * FROM appointments ORDER BY id DESC")
    # База клієнтів згрупована за телефонами та іменами з підрахунком загальної суми
    clients = run_query("""
        SELECT client_name, client_phone, 
               COUNT(id) as total_cars, 
               SUM(CASE WHEN status = 'Виконано' THEN final_price ELSE 0 END) as total_spent,
               STRING_AGG(DISTINCT car_brand || ' ' || car_model, ', ') as cars_list
        FROM appointments 
        GROUP BY client_name, client_phone 
        ORDER BY MAX(created_at) DESC
    """)
    context = {
        "request": request,
        "appointments": rep,
        "clients": clients
    }
    return templates.TemplateResponse(request, "reports.html", context)

@app.get("/backup/export")
async def export_backup():
    tables = ["services", "inventory", "appointments", "appointment_photos", "appointment_services", "appointment_spoiled", "film_usage"]
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
@app.get("/appointment/{app_id}", response_class=HTMLResponse)
async def appointment_detail(request: Request, app_id: int):
    # Отримуємо дані запису
    app = run_query("SELECT * FROM appointments WHERE id = %s", (app_id,))
    if not app:
        raise HTTPException(status_code=404, detail="Запис не знайдено")
    
    # Отримуємо доступні матеріали зі складу
    inventory = run_query("SELECT * FROM inventory")
    
    return templates.TemplateResponse(request, "appointment_detail.html", {
        "request": request, 
        "app": app[0],
        "inventory": inventory
    })
