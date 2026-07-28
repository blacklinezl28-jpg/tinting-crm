from datetime import datetime, timedelta
import sqlite3
import pandas as pd
import streamlit as st

# --- Ініціалізація бази даних ---
DB_NAME = "tinting_crm.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # Таблиця клієнтів та авто
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            car_brand TEXT,
            car_model TEXT,
            car_number TEXT,
            car_year INTEGER
        )
    """)

  # Таблиця послуг
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT,
            default_price REAL
        )
    """)

  # Таблиця складу плівок та матеріалів
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

  # Таблиця записів та фінансів
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            service_id INTEGER,
            film_id INTEGER,
            meters_used REAL,
            total_price REAL,
            payment_type TEXT, -- 'cash' або 'transfer'
            cost_price REAL,
            master_percent REAL,
            master_payout REAL,
            status TEXT, -- 'Заплановано', 'В роботі', 'Виконано', 'Скасовано'
            date TEXT,
            time TEXT,
            warranty_months INTEGER,
            photo_path TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id),
            FOREIGN KEY(service_id) REFERENCES services(id),
            FOREIGN KEY(film_id) REFERENCES inventory(id)
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


# --- Інтерфейс Streamlit ---
st.set_page_config(
    page_title="Detailing & Tinting CRM", page_icon="🚗", layout="wide"
)

st.sidebar.title("🚗 Меню CRM")
menu = st.sidebar.selectbox(
    "Виберіть розділ",
    [
        "📊 Головний екран (Dashboard)",
        "📅 Записи та Календар",
        "👥 Клієнти та Авто",
        "⚙️ Налаштування послуг",
        "📦 Склад плівок",
        "💰 Фінанси та Звіти",
    ],
)

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

  # Перевірка на залишок менше 3 метрів
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
      """SELECT a.time, s.service_name FROM appointments a 
               JOIN services s ON a.service_id = s.id 
               WHERE a.date = ? AND a.status = 'Заплановано' ORDER BY a.time ASC LIMIT 1""",
      (today_str,),
  )
  next_text = (
      f"{next_app.iloc[0]['time']} — {next_app.iloc[0]['service_name']}"
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

  # Головне сповіщення про плівки, яких залишилося менше 3 метрів
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

  # Пошук за держномером
  st.subheader("🔍 Швидкий пошук авто за держномером")
  search_query = st.text_input(
      "Введіть держномер або частину номера (наприклад, 7777):"
  )
  if search_query:
    found_cars = run_query(
        """SELECT c.name, c.phone, c.car_brand || ' ' || c.car_model as car, c.car_number,
                  s.service_name, a.date, a.warranty_months 
           FROM appointments a
           JOIN clients c ON a.client_id = c.id
           JOIN services s ON a.service_id = s.id
           WHERE c.car_number LIKE ?""",
        (f"%{search_query}%",),
    )
    if not found_cars.empty:
      st.dataframe(found_cars, use_container_width=True)
    else:
      st.info("Автомобілів за таким номером не знайдено.")

  st.subheader("📊 Динаміка прибутків")
  df_all_done = run_query("""
        SELECT date, total_price, (total_price - cost_price - master_payout) as profit 
        FROM appointments WHERE status = 'Виконано'
    """)
  if not df_all_done.empty:
    df_all_done["date"] = pd.to_datetime(df_all_done["date"])
    df_grouped = (
        df_all_done.groupby("date")[["total_price", "profit"]].sum().reset_index()
    )
    df_grouped = df_grouped.set_index("date")
    st.line_chart(df_grouped, color=["#2ecc71", "#3498db"])
  else:
    st.info("Ще немає завершених замовлень для графіків.")


# ==========================================
# 2. ЗАПИСИ ТА КАЛЕНДАР
# ==========================================
elif menu == "📅 Записи та Календар":
  st.title("📅 Керування записами")

  with st.expander("➕ Додати новий запис / послугу"):
    clients_df = run_query(
        "SELECT id, name, phone, car_brand, car_model, car_number FROM clients"
    )
    services_df = run_query("SELECT id, service_name, default_price FROM services")
    inventory_df = run_query("SELECT id, film_name, meters_left FROM inventory")

    client_options = (
        {
            f"{row['name']} ({row['car_brand']} {row['car_model']} [{row['car_number']}])": row[
                "id"
            ]
            for _, row in clients_df.iterrows()
        }
        if not clients_df.empty
        else {}
    )

    service_options = (
        {
            f"{row['service_name']} ({row['default_price']} грн)": row["id"]
            for _, row in services_df.iterrows()
        }
        if not services_df.empty
        else {}
    )

    film_options = (
        {
            f"{row['film_name']} (Залишок: {row['meters_left']} м)": row["id"]
            for _, row in inventory_df.iterrows()
        }
        if not inventory_df.empty
        else {}
    )

    with st.form("add_appointment_form"):
      st.subheader("Деталі візиту")
      if client_options:
        selected_client_label = st.selectbox(
            "Клієнт та авто", list(client_options.keys())
        )
        client_id = client_options[selected_client_label]
      else:
        client_id = None
        st.warning("Спочатку додайте клієнта у вкладці 'Клієнти та Авто'!")

      if service_options:
        selected_service_label = st.selectbox(
            "Послуга", list(service_options.keys())
        )
        service_id = service_options[selected_service_label]
      else:
        service_id = None
        st.warning("Додайте послуги у вкладці 'Налаштування послуг'!")

      use_film = st.checkbox(
          "Використовувати плівку зі складу (тонування / бронеплівка)"
      )
      film_id = None
      meters_used = 0.0

      if use_film and film_options:
        selected_film_label = st.selectbox(
            "Вибрати плівку", list(film_options.keys())
        )
        film_id = film_options[selected_film_label]
        meters_used = st.number_input(
            "Витрата плівки (пог. метрів)", min_value=0.1, value=2.0, step=0.1
        )

      total_price = st.number_input(
          "Підсумкова ціна для клієнта (грн)",
          min_value=0.0,
          value=3000.0,
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

      st.subheader("Зарплата майстра та додатково")
      master_percent = st.slider(
          "Відсоток майстра від роботи (%)", min_value=0, max_value=60, value=30
      )
      warranty_months = st.number_input(
          "Гарантія (місяців)", min_value=0, value=12, step=1
      )
      photo_file = st.file_uploader(
          "Фотофіксація (До / Після)", type=["jpg", "png", "jpeg"]
      )

      date = st.date_input("Дата візиту", value=datetime.now())
      time = st.time_input("Час візиту", value=datetime.now().time())

      submitted = st.form_submit_button("Зберегти запис")
      if submitted and client_id and service_id:
        cost_price = 0.0
        if film_id and meters_used > 0:
          film_info = run_query(
              "SELECT cost_per_meter, meters_left FROM inventory WHERE id = ?",
              (film_id,),
          )
          cost_per_meter = film_info.iloc[0]["cost_per_meter"]
          current_meters = film_info.iloc[0]["meters_left"]
          cost_price = meters_used * cost_per_meter

          if status in ["В роботі", "Виконано"]:
            new_meters = max(0.0, current_meters - meters_used)
            run_query(
                "UPDATE inventory SET meters_left = ? WHERE id = ?",
                (new_meters, film_id),
                fetch=False,
            )

        master_payout = total_price * (master_percent / 100.0)

        photo_path = ""
        if photo_file is not None:
          photo_path = f"saved_{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo_file.name}"
          with open(photo_path, "wb") as f:
            f.write(photo_file.getbuffer())

        run_query(
            """INSERT INTO appointments (client_id, service_id, film_id, meters_used, 
                   total_price, payment_type, cost_price, master_percent, master_payout, 
                   status, date, time, warranty_months, photo_path) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                client_id,
                service_id,
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
            fetch=False,
        )

        st.success("Запис успішно створено!")
        st.rerun()

  st.subheader("Список усіх записів")
  app_list = run_query("""
        SELECT a.id, c.name, c.car_brand || ' ' || c.car_model as car, c.car_number,
               s.service_name, a.total_price, a.payment_type, a.status, a.date, a.time, a.warranty_months
        FROM appointments a
        JOIN clients c ON a.client_id = c.id
        JOIN services s ON a.service_id = s.id
        ORDER BY a.date DESC, a.time DESC
    """)
  if not app_list.empty:
    st.dataframe(app_list, use_container_width=True)
  else:
    st.info("Ще немає жодного запису.")


# ==========================================
# 3. КЛІЄНТИ ТА АВТОМОБІЛІ
# ==========================================
elif menu == "👥 Клієнти та Авто":
  st.title("👥 База клієнтів та автомобілів")

  with st.expander("➕ Додати нового клієнта"):
    with st.form("add_client_form"):
      name = st.text_input("Ім'я клієнта")
      phone = st.text_input("Телефон")
      car_brand = st.text_input("Марка авто (наприклад, Audi)")
      car_model = st.text_input("Модель авто (наприклад, A6)")
      car_number = st.text_input(
          "Державний номер авто (наприклад, КА7777ВХ)"
      ).upper()
      car_year = st.number_input("Рік випуску", min_value=1990, max_value=2026, value=2022)

      submitted_client = st.form_submit_button("Зберегти клієнта")
      if submitted_client and name:
        run_query(
            """INSERT INTO clients (name, phone, car_brand, car_model, car_number, car_year) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
            (name, phone, car_brand, car_model, car_number, car_year),
            fetch=False,
        )
        st.success(f"Клієнта {name} додано!")
        st.rerun()

  st.subheader("Усі клієнти")
  clients_df = run_query("SELECT * FROM clients")
  if not clients_df.empty:
    st.dataframe(clients_df, use_container_width=True)
  else:
    st.info("База клієнтів порожня.")


# ==========================================
# 4. НАЛАШТУВАННЯ ПОСЛУГ
# ==========================================
elif menu == "⚙️ Налаштування послуг":
  st.title("⚙️ Керування послугами")

  with st.expander("➕ Додати нову послугу"):
    with st.form("add_service_form"):
      service_name = st.text_input(
          "Назва послуги (наприклад, Хімчистка салону, Мийка люкс)"
      )
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

  st.subheader("Список доступних послуг")
  services_df = run_query("SELECT * FROM services")
  if not services_df.empty:
    st.dataframe(services_df, use_container_width=True)
  else:
    st.info("Немає доданих послуг.")


# ==========================================
# 5. СКЛАД ПЛІВОК
# ==========================================
elif menu == "📦 Склад плівок":
  st.title("📦 Облік плівок та матеріалів")

  with st.expander("➕ Додати нову позицію на склад"):
    with st.form("add_film_form"):
      film_name = st.text_input("Назва плівки (наприклад, Llumar PPF / UltraVision 5%)")
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
          "Мінімальний залишок (попередження)", min_value=0.0, value=5.0, step=1.0
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
# 6. ФІНАНСИ ТА ЗВІТИ
# ==========================================
elif menu == "💰 Фінанси та Звіти":
  st.title("💰 Фінансові звіти")

  fin_data = run_query("""
        SELECT a.date, s.service_name, a.total_price, a.cost_price, a.master_payout,
               (a.total_price - a.cost_price - a.master_payout) as net_profit, 
               a.payment_type, a.status
        FROM appointments a
        JOIN services s ON a.service_id = s.id
        WHERE a.status = 'Виконано'
        ORDER BY a.date DESC
    """)

  if not fin_data.empty:
    total_rev = fin_data["total_price"].sum()
    total_prof = fin_data["net_profit"].sum()

    col1, col2 = st.columns(2)
    col1.metric("Загальний дохід", f"{total_rev:,.0f} грн")
    col2.metric("Чистий прибуток (після всіх витрат)", f"{total_prof:,.0f} грн")

    st.divider()
    st.subheader("Детальна історія закритих замовлень")
    st.dataframe(fin_data, use_container_width=True)
  else:
    st.info("Немає даних для фінансових звітів.")
