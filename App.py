from datetime import datetime, timedelta
import os
import sqlite3
import pandas as pd
import streamlit as st

# --- Ініціалізація бази даних ---
DB_NAME = "tinting_crm.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            car_brand TEXT,
            car_model TEXT,
            car_number TEXT,
            car_year INTEGER,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT,
            default_price REAL
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            film_name TEXT,
            category TEXT,
            meters_left REAL,
            min_limit REAL,
            cost_per_meter REAL
        )
    """)

  # Таблиця додаткових розхідників
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS supplies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT,
            quantity REAL,
            unit TEXT,
            cost REAL
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            car_id INTEGER,
            film_id INTEGER,
            meters_used REAL,
            total_price REAL,
            payment_type TEXT,
            cost_price REAL,
            master_percent REAL,
            master_payout REAL,
            status TEXT,
            date TEXT,
            time TEXT,
            warranty_months INTEGER,
            photo_path TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id),
            FOREIGN KEY(car_id) REFERENCES cars(id),
            FOREIGN KEY(film_id) REFERENCES inventory(id)
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointment_services (
            appointment_id INTEGER,
            service_id INTEGER,
            FOREIGN KEY(appointment_id) REFERENCES appointments(id),
            FOREIGN KEY(service_id) REFERENCES services(id)
        )
    """)

  cursor.execute("SELECT COUNT(*) FROM services")
  if cursor.fetchone()[0] == 0:
    default_services = [
        ("Тонування задньої півсфери", 2500.0),
        ("Тонування лобового скла", 1500.0),
        ("Бронеплівка на фари", 1800.0),
        ("Бронеплівка (зони ризику: капот, крила)", 6000.0),
    ]
    cursor.executemany(
        "INSERT INTO services (service_name, default_price) VALUES (?, ?)",
        default_services,
    )

  conn.commit()
  conn.close()


init_db()


def run_query(query, params=(), fetch=True):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute(query, params)
  if fetch:
    data = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    conn.close()
    return pd.DataFrame(data, columns=columns)
  else:
    conn.commit()
    conn.close()


st.set_page_config(
    page_title="Detailing & Tinting CRM", page_icon="🚗", layout="wide"
)

# --- Налаштування додаткових функцій у сайдбарі ---
st.sidebar.title("🚗 Меню CRM")

st.sidebar.divider()
st.sidebar.subheader("⚙️ Увімкнення функцій")
enable_photos = st.sidebar.checkbox("📸 Фотофіксація авто", value=True)
enable_salaries = st.sidebar.checkbox("💵 Зарплата майстрів", value=True)
enable_supplies = st.sidebar.checkbox("🧴 Облік розхідників", value=True)

menu_options = [
    "📊 Головний екран (Dashboard)",
    "📅 Записи та Календар",
    "👥 Клієнти та Авто",
    "⚙️ Налаштування послуг",
    "📦 Склад плівок",
]

if enable_supplies:
  menu_options.append("🧴 Розхідні матеріали")
if enable_salaries:
  menu_options.append("💵 Зарплата майстрів")

menu_options.append("💰 Фінанси та Звіти")

menu = st.sidebar.selectbox("Виберіть розділ", menu_options)

today_str = datetime.now().strftime("%Y-%m-%d")

# ==========================================
# 1. ГОЛОВНИЙ ЕКРАН (DASHBOARD)
# ==========================================
if menu == "📊 Головний екран (Dashboard)":
  st.title("📊 Головний екран")
  st.write(f"Сьогодні: **{datetime.now().strftime('%d.%m.%Y')}**")

  df_today = run_query(
      "SELECT * FROM appointments WHERE date = ? AND status = 'Виконано'",
      (today_str,),
  )

  cash_today = (
      df_today[df_today["payment_type"] == "cash"]["total_price"].sum()
      if not df_today.empty
      else 0.0
  )
  transfer_today = (
      df_today[df_today["payment_type"] == "transfer"]["total_price"].sum()
      if not df_today.empty
      else 0.0
  )

  total_revenue_today = (
      df_today["total_price"].sum() if not df_today.empty else 0.0
  )
  total_cost_today = (
      df_today["cost_price"].sum() if not df_today.empty else 0.0
  )
  total_master_today = (
      df_today["master_payout"].sum() if not df_today.empty else 0.0
  )
  profit_today = total_revenue_today - total_cost_today - total_master_today

  df_all_today = run_query(
      "SELECT * FROM appointments WHERE date = ?", (today_str,)
  )
  appointments_count = len(df_all_today)

  df_in_progress = run_query(
      "SELECT * FROM appointments WHERE date = ? AND status = 'В роботі'",
      (today_str,),
  )
  cars_in_work = len(df_in_progress)

  df_critical_stock = run_query(
      "SELECT film_name, meters_left FROM inventory WHERE meters_left < 3.0"
  )

  col1, col2, col3, col4 = st.columns(4)
  col1.metric("💰 Каса сьогодні", f"{cash_today:,.0f} грн")
  col2.metric("💳 Перекази сьогодні", f"{transfer_today:,.0f} грн")
  col3.metric("📈 Чистий прибуток", f"{profit_today:,.0f} грн")
  col4.metric("📅 Записів сьогодні", f"{appointments_count}")

  col5, col6, col7 = st.columns(3)
  col5.metric("🚗 Авто в роботі", f"{cars_in_work}")

  next_app = run_query(
      """SELECT a.time, c.car_brand || ' ' || c.car_model as car FROM appointments a 
               JOIN cars c ON a.car_id = c.id 
               WHERE a.date = ? AND a.status = 'Заплановано' ORDER BY a.time ASC LIMIT 1""",
      (today_str,),
  )
  next_text = (
      f"{next_app.iloc[0]['time']} — {next_app.iloc[0]['car']}"
      if not next_app.empty
      else "Немає запланованих"
  )
  col6.metric("⏰ Найближчий запис", next_text)

  stock_status_text = (
      f"⚠️ {len(df_critical_stock)} поз. < 3м!"
      if not df_critical_stock.empty
      else "Все ОК"
  )
  col7.metric("📦 Склад (< 3м)", stock_status_text)

  st.divider()

  if not df_critical_stock.empty:
    st.error(
        "🚨 **УВАГА! Наступні позиції плівок закінчуються (залишилось менше 3"
        " метрів):**"
    )
    for _, row in df_critical_stock.iterrows():
      st.warning(
          f"🔹 **{row['film_name']}** — залишилося всього **{row['meters_left']}"
          " м**!"
      )

  st.subheader("🔍 Швидкий пошук авто за держномером")
  search_query = st.text_input(
      "Введіть держномер або частину номера (наприклад, 7777):"
  )
  if search_query:
    found_cars = run_query(
        """SELECT cl.name, cl.phone, c.car_brand || ' ' || c.car_model as car, c.car_number,
                  a.date, a.status, a.total_price 
           FROM appointments a
           JOIN clients cl ON a.client_id = cl.id
           JOIN cars c ON a.car_id = c.id
           WHERE c.car_number LIKE ?""",
        (f"%{search_query}%",),
    )
    if not found_cars.empty:
      st.dataframe(found_cars, use_container_width=True)
    else:
      st.info("Автомобілів за таким номером не знайдено.")


# ==========================================
# 2. ЗАПИСИ ТА КАЛЕНДАР
# ==========================================
elif menu == "📅 Записи та Календар":
  st.title("📅 Керування записами")

  with st.expander("➕ Створити новий запис (з авто і клієнтом)"):
    services_df = run_query("SELECT id, service_name, default_price FROM services")
    inventory_df = run_query("SELECT id, film_name, meters_left FROM inventory")

    with st.form("add_appointment_form"):
      st.subheader("1. Контактні дані клієнта")
      client_name = st.text_input("Ім'я клієнта")
      client_phone = st.text_input("Телефон клієнта")

      st.subheader("2. Дані автомобіля")
      car_brand = st.text_input("Марка авто (наприклад, BMW)")
      car_model = st.text_input("Модель авто (наприклад, X5)")
      car_number = st.text_input(
          "Державний номер (наприклад, КА7777ВХ)"
      ).upper()
      car_year = st.number_input(
          "Рік випуску", min_value=1990, max_value=2026, value=2022
      )

      st.subheader("3. Вибір послуг (можна вибрати кілька)")
      selected_services = []
      if not services_df.empty:
        for _, s_row in services_df.iterrows():
          if st.checkbox(
              f"{s_row['service_name']} ({s_row['default_price']} грн)",
              key=f"srv_{s_row['id']}",
          ):
            selected_services.append(s_row["id"])
      else:
        st.warning("Спочатку додайте послуги у налаштуваннях!")

      st.subheader("4. Плівка та матеріали")
      use_film = st.checkbox("Використовувати плівку зі складу")
      film_id = None
      meters_used = 0.0

      film_options = (
          {
              f"{row['film_name']} (Залишок: {row['meters_left']} м)": row[
                  "id"
              ]
              for _, row in inventory_df.iterrows()
          }
          if not inventory_df.empty
          else {}
      )

      if use_film and film_options:
        selected_film_label = st.selectbox(
            "Виберіть плівку", list(film_options.keys())
        )
        film_id = film_options[selected_film_label]
        meters_used = st.number_input(
            "Витрата плівки (пог. метрів)", min_value=0.1, value=2.0, step=0.1
        )

      total_price = st.number_input(
          "Загальна ціна для клієнта (грн)",
          min_value=0.0,
          value=3500.0,
          step=100.0,
      )

      col_p1, col_p2 = st.columns(2)
      with col_p1:
        payment_type = st.selectbox(
            "Тип оплати",
            options=["cash", "transfer"],
            format_func=lambda x: (
                "Готівка (Каса)" if x == "cash" else "Переказ (Карта/IBAN)"
            ),
        )
      with col_p2:
        status = st.selectbox(
            "Статус", ["Заплановано", "В роботі", "Виконано", "Скасовано"]
        )

      master_percent = st.slider(
          "Відсоток майстра від роботи (%)", min_value=0, max_value=60, value=30
      )
      warranty_months = st.number_input(
          "Гарантія (місяців)", min_value=0, value=12, step=1
      )

      photo_file = None
      if enable_photos:
        photo_file = st.file_uploader(
            "📸 Фотофіксація авто (До / Після)", type=["jpg", "png", "jpeg"]
        )

      date = st.date_input("Дата візиту", value=datetime.now())
      time = st.time_input("Час візиту", value=datetime.now().time())

      submitted = st.form_submit_button("Зберегти запис та авто")

      if submitted and client_name and car_brand and selected_services:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO clients (name, phone) VALUES (?, ?)",
            (client_name, client_phone),
        )
        client_id = cursor.lastrowid

        cursor.execute(
            """INSERT INTO cars (client_id, car_brand, car_model, car_number, car_year) 
                   VALUES (?, ?, ?, ?, ?)""",
            (client_id, car_brand, car_model, car_number, car_year),
        )
        car_id = cursor.lastrowid

        cost_price = 0.0
        if film_id and meters_used > 0:
          cursor.execute(
              "SELECT cost_per_meter, meters_left FROM inventory WHERE id = ?",
              (film_id,),
          )
          f_row = cursor.fetchone()
          if f_row:
            cost_per_meter, current_meters = f_row[0], f_row[1]
            cost_price = meters_used * cost_per_meter

            if status in ["В роботі", "Виконано"]:
              new_meters = max(0.0, current_meters - meters_used)
              cursor.execute(
                  "UPDATE inventory SET meters_left = ? WHERE id = ?",
                  (new_meters, film_id),
              )

        master_payout = total_price * (master_percent / 100.0)

        photo_path = ""
        if enable_photos and photo_file is not None:
          os.makedirs("uploads", exist_ok=True)
          photo_path = f"uploads/{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo_file.name}"
          with open(photo_path, "wb") as f:
            f.write(photo_file.getbuffer())

        cursor.execute(
            """INSERT INTO appointments (client_id, car_id, film_id, meters_used, 
                   total_price, payment_type, cost_price, master_percent, master_payout, 
                   status, date, time, warranty_months, photo_path) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                client_id,
                car_id,
                film_id,
                meters_used,
                total_price,
                payment_type,
                cost_price,
                master_percent,
                master_payout,
                status,
                str(date),
                str(time),
                warranty_months,
                photo_path,
            ),
        )
        appointment_id = cursor.lastrowid

        for s_id in selected_services:
          cursor.execute(
              "INSERT INTO appointment_services (appointment_id, service_id)"
              " VALUES (?, ?)",
              (appointment_id, s_id),
          )

        conn.commit()
        conn.close()

        st.success("Запис успішно збережено!")
        st.rerun()

  st.divider()
  st.subheader("📋 Список усіх записів та редагування")

  appointments_df = run_query("""
        SELECT a.id, cl.name as client, c.car_brand || ' ' || c.car_model as car, 
               c.car_number, a.total_price, a.status, a.date, a.time, a.photo_path
        FROM appointments a
        JOIN clients cl ON a.client_id = cl.id
        JOIN cars c ON a.car_id = c.id
        ORDER BY a.date DESC, a.time DESC
    """)

  if not appointments_df.empty:
    for _, row in appointments_df.iterrows():
      with st.expander(
          f"📅 {row['date']} {row['time']} | {row['client']} — {row['car']} ({row['car_number']}) | Статус: {row['status']} | Сума: {row['total_price']} грн"
      ):
        if enable_photos and row["photo_path"] and os.path.exists(row["photo_path"]):
          st.image(row["photo_path"], caption="Фото автомобіля", width=300)

        with st.form(f"edit_app_{row['id']}"):
          new_status = st.selectbox(
              "Змінити статус",
              ["Заплановано", "В роботі", "Виконано", "Скасовано"],
              index=[
                  "Заплановано",
                  "В роботі",
                  "Виконано",
                  "Скасовано",
              ].index(row["status"]),
          )
          new_price = st.number_input(
              "Ціна (грн)", value=float(row["total_price"]), step=100.0
          )

          update_btn = st.form_submit_button("Оновити запис")
          if update_btn:
            run_query(
                "UPDATE appointments SET status = ?, total_price = ? WHERE id ="
                " ?",
                (new_status, new_price, row["id"]),
                fetch=False,
            )
            st.success("Запис успішно оновлено!")
            st.rerun()
  else:
    st.info("Ще немає записів.")


# ==========================================
# 3. КЛІЄНТИ ТА АВТОМОБІЛІ
# ==========================================
elif menu == "👥 Клієнти та Авто":
  st.title("👥 База клієнтів, їхні авто та витрати")

  clients_df = run_query("SELECT * FROM clients")

  if not clients_df.empty:
    for _, client in clients_df.iterrows():
      with st.expander(f"👤 {client['name']} (Тел: {client['phone']})"):
        cars_df = run_query(
            "SELECT * FROM cars WHERE client_id = ?", (client["id"],)
        )
        spent_df = run_query(
            """SELECT SUM(total_price) as total_spent 
               FROM appointments WHERE client_id = ? AND status = 'Виконано'""",
            (client["id"],),
        )
        total_spent = (
            spent_df.iloc[0]["total_spent"]
            if not spent_df.empty and pd.notna(spent_df.iloc[0]["total_spent"])
            else 0.0
        )

        st.write(
            f"💰 **Загалом витрачено клієнтом:** `{total_spent:,.0f} грн`"
        )
        st.write("🚗 **Автомобілі клієнта:**")

        if not cars_df.empty:
          st.dataframe(cars_df, use_container_width=True)
        else:
          st.info("У цього клієнта поки немає зареєстрованих авто.")
  else:
    st.info("База клієнтів порожня.")


# ==========================================
# 4. НАЛАШТУВАННЯ ПОСЛУГ
# ==========================================
elif menu == "⚙️ Налаштування послуг":
  st.title("⚙️ Керування послугами та цінами")

  with st.expander("➕ Додати нову послугу"):
    with st.form("add_service_form"):
      service_name = st.text_input("Назва послуги")
      default_price = st.number_input(
          "Базова вартість (грн)", min_value=0.0, value=1000.0, step=100.0
      )

      submitted_service = st.form_submit_button("Додати послугу")
      if submitted_service and service_name:
        run_query(
            "INSERT INTO services (service_name, default_price) VALUES (?, ?)",
            (service_name, default_price),
            fetch=False,
        )
        st.success("Нову послугу успішно додано!")
        st.rerun()

  st.subheader("Редагування існуючих послуг")
  services_df = run_query("SELECT * FROM services")

  if not services_df.empty:
    for _, s_row in services_df.iterrows():
      with st.form(f"edit_srv_{s_row['id']}"):
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
          upd_name = st.text_input(
              "Назва послуги", value=s_row["service_name"], key=f"name_{s_row['id']}"
          )
        with col_s2:
          upd_price = st.number_input(
              "Ціна (грн)",
              value=float(s_row["default_price"]),
              step=50.0,
              key=f"prc_{s_row['id']}",
          )

        col_b1, col_b2 = st.columns(2)
        with col_b1:
          save_s = st.form_submit_button("💾 Зберегти зміни")
        with col_b2:
          del_s = st.form_submit_button("🗑️ Видалити послугу")

        if save_s:
          run_query(
              "UPDATE services SET service_name = ?, default_price = ? WHERE id"
              " = ?",
              (upd_name, upd_price, s_row["id"]),
              fetch=False,
          )
          st.success("Послугу оновлено!")
          st.rerun()

        if del_s:
          run_query(
              "DELETE FROM services WHERE id = ?", (s_row["id"],), fetch=False
          )
          st.warning("Послугу видалено!")
          st.rerun()
  else:
    st.info("Немає доданих послуг.")


# ==========================================
# 5. СКЛАД ПЛІВОК
# ==========================================
elif menu == "📦 Склад плівок":
  st.title("📦 Облік плівок та матеріалів")

  with st.expander("➕ Додати нову позицію на склад"):
    with st.form("add_film_form"):
      film_name = st.text_input("Назва плівки")
      category = st.selectbox(
          "Категорія",
          [
              "Поліуретан (Фари/Кузов)",
              "Тонувальна плівка",
              "Атермальна плівка",
              "Розхідники",
          ],
      )
      meters_left = st.number_input(
          "Кількість на складі (пог. метрів)", min_value=0.0, value=30.0, step=1.0
      )
      min_limit = st.number_input(
          "Мінімальний залишок", min_value=0.0, value=5.0, step=1.0
      )
      cost_per_meter = st.number_input(
          "Собівартість 1 метра (грн)", min_value=0.0, value=250.0, step=10.0
      )

      submitted_film = st.form_submit_button("Додати на склад")
      if submitted_film and film_name:
        run_query(
            """INSERT INTO inventory (film_name, category, meters_left, min_limit, cost_per_meter) 
                   VALUES (?, ?, ?, ?, ?)""",
            (film_name, category, meters_left, min_limit, cost_per_meter),
            fetch=False,
        )
        st.success("Матеріал додано на склад!")
        st.rerun()

  st.subheader("Залишки на складі")
  inventory_df = run_query("SELECT * FROM inventory")
  if not inventory_df.empty:
    st.dataframe(inventory_df, use_container_width=True)
  else:
    st.info("Склад порожній.")


# ==========================================
# 6. РОЗХІДНІ МАТЕРІАЛИ (якщо увімкнено)
# ==========================================
elif enable_supplies and menu == "🧴 Розхідні матеріали":
  st.title("🧴 Облік дрібних розхідників (знежирювач, серветки, леза)")

  with st.expander("➕ Додати розхідник"):
    with st.form("add_supply_form"):
      item_name = st.text_input("Назва матеріалу")
      quantity = st.number_input("Кількість", min_value=0.0, value=10.0)
      unit = st.selectbox("Одиниця виміру", ["шт", "л", "упак", "м"])
      cost = st.number_input("Загальна вартість (грн)", min_value=0.0, value=500.0)

      sub_sup = st.form_submit_button("Додати")
      if sub_sup and item_name:
        run_query(
            "INSERT INTO supplies (item_name, quantity, unit, cost) VALUES (?,"
            " ?, ?, ?)",
            (item_name, quantity, unit, cost),
            fetch=False,
        )
        st.success("Розхідник додано!")
        st.rerun()

  st.subheader("Наявні розхідники")
  supplies_df = run_query("SELECT * FROM supplies")
  if not supplies_df.empty:
    st.dataframe(supplies_df, use_container_width=True)
  else:
    st.info("Список розхідників порожній.")


# ==========================================
# 7. ЗАРПЛАТА МАЙСТРІВ (якщо увімкнено)
# ==========================================
elif enable_salaries and menu == "💵 Зарплата майстрів":
  st.title("💵 Розрахунок зарплати майстрів")

  master_data = run_query("""
        SELECT a.date, c.car_brand || ' ' || c.car_model as car, 
               a.total_price, a.master_percent, a.master_payout, a.status
        FROM appointments a
        JOIN cars c ON a.car_id = c.id
        WHERE a.status = 'Виконано'
        ORDER BY a.date DESC
    """)

  if not master_data.empty:
    total_salaries = master_data["master_payout"].sum()
    st.metric(
        "💰 Загальна сума виплат майстрам (за виконані)",
        f"{total_salaries:,.0f} грн",
    )
    st.divider()
    st.subheader("Деталізація по замовленнях")
    st.dataframe(master_data, use_container_width=True)
  else:
    st.info("Немає завершених замовлень для розрахунку зарплати.")


# ==========================================
# 8. ФІНАНСИ ТА ЗВІТИ
# ==========================================
elif menu == "💰 Фінанси та Звіти":
  st.title("💰 Фінансові звіти")

  fin_data = run_query("""
        SELECT a.date, a.total_price, a.cost_price, a.master_payout,
               (a.total_price - a.cost_price - a.master_payout) as net_profit, 
               a.payment_type, a.status
        FROM appointments a
        WHERE a.status = 'Виконано'
        ORDER BY a.date DESC
    """)

  if not fin_data.empty:
    total_rev = fin_data["total_price"].sum()
    total_prof = fin_data["net_profit"].sum()

    col1, col2 = st.columns(2)
    col1.metric("Загальний дохід", f"{total_rev:,.0f} грн")
    col2.metric("Чистий прибуток", f"{total_prof:,.0f} грн")

    st.divider()
    st.subheader("Детальна історія закритих замовлень")
    st.dataframe(fin_data, use_container_width=True)
  else:
    st.info("Немає даних для фінансових звітів.")
