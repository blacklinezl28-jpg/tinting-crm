from datetime import datetime
import os
import sqlite3
import pandas as pd
import streamlit as st

# --- Конфігурація сторінки ---
st.set_page_config(
    page_title="Detailing & Tinting CRM", page_icon="🚗", layout="wide"
)

# --- Налаштування безпеки (Пароль) ---
SYSTEM_PASSWORD = "blzl"  # <--- Змініть за потреби


def check_password():
  if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

  if not st.session_state["authenticated"]:
    st.title("🔒 Авторизація в CRM-системі")
    st.write(
        "Введіть пароль для доступу до бази даних та управління студією:"
    )

    entered_password = st.text_input("Пароль", type="password")
    if st.button("Увійти"):
      if entered_password == SYSTEM_PASSWORD:
        st.session_state["authenticated"] = True
        st.rerun()
      else:
        st.error("Невірний пароль!")
    return False
  return True


if not check_password():
  st.stop()

# --- Ініціалізація та міграція бази даних ---
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
            FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE
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
            width_cm REAL,
            meters_left REAL,
            min_limit REAL,
            price_usd REAL,
            exchange_rate REAL,
            cost_per_meter_uah REAL
        )
    """)

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
            supply_id INTEGER,
            supply_qty REAL,
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
            comment TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY(car_id) REFERENCES cars(id) ON DELETE CASCADE,
            FOREIGN KEY(film_id) REFERENCES inventory(id) ON DELETE SET NULL,
            FOREIGN KEY(supply_id) REFERENCES supplies(id) ON DELETE SET NULL
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointment_services (
            appointment_id INTEGER,
            service_id INTEGER,
            FOREIGN KEY(appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
            FOREIGN KEY(service_id) REFERENCES services(id) ON DELETE CASCADE
        )
    """)

  # Безпечна міграція відсутніх колонок
  cursor.execute("PRAGMA table_info(appointments)")
  columns = [col[1] for col in cursor.fetchall()]

  if "supply_id" not in columns:
    cursor.execute("ALTER TABLE appointments ADD COLUMN supply_id INTEGER")
  if "supply_qty" not in columns:
    cursor.execute("ALTER TABLE appointments ADD COLUMN supply_qty REAL")
  if "photo_path" not in columns:
    cursor.execute("ALTER TABLE appointments ADD COLUMN photo_path TEXT")
  if "comment" not in columns:
    cursor.execute("ALTER TABLE appointments ADD COLUMN comment TEXT")
  if "master_percent" not in columns:
    cursor.execute(
        "ALTER TABLE appointments ADD COLUMN master_percent REAL DEFAULT 15.0"
    )

  cursor.execute("SELECT COUNT(*) FROM services")
  if cursor.fetchone()[0] == 0:
    default_services = [
        ("Тонування задньої півсфери", 2500.0),
        ("Тонування лобового скла", 1500.0),
        ("Бронеплівка на фари", 1800.0),
        ("Бронеплівка (зони ризику)", 6000.0),
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


st.sidebar.title("🚗 Меню CRM")
st.sidebar.divider()

menu = st.sidebar.selectbox(
    "Виберіть розділ",
    [
        "📊 Головний екран (Dashboard)",
        "📅 Записи та Календар",
        "👥 Клієнти та Авто",
        "📦 Склад (Плівки та Розхідники)",
        "💵 Зарплата майстрів",
        "💰 Фінанси та Звіти",
        "⚙️ Налаштування послуг",
        "⚙️ Налаштування системи",
    ],
)

today_str = datetime.now().strftime("%Y-%m-%d")
current_month_prefix = datetime.now().strftime("%Y-%m")

# ==========================================
# 1. ГОЛОВНИЙ ЕКРАН (DASHBOARD)
# ==========================================
if menu == "📊 Головний екран (Dashboard)":
  st.title("📊 Головний екран")
  st.write(f"Сьогодні: **{datetime.now().strftime('%d.%m.%Y')}**")

  df_today = run_query(
      "SELECT SUM(total_price) as sum FROM appointments WHERE date = ? AND status ='Виконано'",
      (today_str,),
  )
  cash_today = (
      df_today.iloc[0]["sum"]
      if not df_today.empty and pd.notna(df_today.iloc[0]["sum"])
      else 0.0
  )

  df_month = run_query(
      "SELECT SUM(total_price) as sum FROM appointments WHERE date LIKE ? AND status = 'Виконано'",
      (f"{current_month_prefix}%",),
  )
  cash_month = (
      df_month.iloc[0]["sum"]
      if not df_month.empty and pd.notna(df_month.iloc[0]["sum"])
      else 0.0
  )

  df_prof_month = run_query(
      """SELECT SUM(total_price - cost_price - master_payout) as profit 
         FROM appointments WHERE date LIKE ? AND status = 'Виконано'""",
      (f"{current_month_prefix}%",),
  )
  profit_month = (
      df_prof_month.iloc[0]["profit"]
      if not df_prof_month.empty
      and pd.notna(df_prof_month.iloc[0]["profit"])
      else 0.0
  )

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
      "SELECT film_name, width_cm, meters_left FROM inventory WHERE meters_left < 3.0"
  )

  col1, col2, col3, col4 = st.columns(4)
  col1.metric("💰 Каса сьогодні", f"{cash_today:,.0f} грн")
  col2.metric("📅 Каса за місяць", f"{cash_month:,.0f} грн")
  col3.metric("📈 Прибуток (місяць)", f"{profit_month:,.0f} грн")
  col4.metric("🚗 Записів сьогодні", f"{appointments_count}")

  col5, col6, col7 = st.columns(3)
  col5.metric("🛠️ В роботі зараз", f"{cars_in_work}")

  next_app = run_query(
      """SELECT a.time, c.car_brand || ' ' || c.car_model as car FROM appointments a 
               JOIN cars c ON a.car_id = c.id 
               WHERE a.date = ? AND a.status = 'Заплановано' ORDER BY a.time ASC LIMIT 1""",
      (today_str,),
  )
  if not next_app.empty:
    raw_time = str(next_app.iloc[0]["time"])
    short_time = raw_time[:5] if len(raw_time) >= 5 else raw_time
    next_text = f"{short_time} — {next_app.iloc[0]['car']}"
  else:
    next_text = "Немає"

  col6.metric("⏰ Найближчий запис", next_text)

  stock_status_text = (
      f"⚠️ {len(df_critical_stock)} поз. < 3м!"
      if not df_critical_stock.empty
      else "Все ОК"
  )
  col7.metric("📦 Склад плівок", stock_status_text)

  st.divider()

  if not df_critical_stock.empty:
    st.error("🚨 **УВАГА! Деякі рулони плівки закінчуються (менше 3 метрів):**")
    for _, row in df_critical_stock.iterrows():
      st.warning(
          f"🔹 **{row['film_name']}** (ширина {row['width_cm']} см) — залишилося"
          f" всього **{row['meters_left']} м**!"
      )


# ==========================================
# 2. ЗАПИСИ ТА КАЛЕНДАР
# ==========================================
elif menu == "📅 Записи та Календар":
  st.title("📅 Керування записами та розрахунок собівартості")

  with st.expander("➕ Створити новий запис"):
    services_df = run_query("SELECT id, service_name, default_price FROM services")
    inventory_df = run_query(
        "SELECT id, film_name, width_cm, meters_left, cost_per_meter_uah FROM"
        " inventory"
    )
    supplies_df_list = run_query(
        "SELECT id, item_name, quantity, cost FROM supplies"
    )

    with st.form("add_appointment_form"):
      st.subheader("1. Дані клієнта")
      client_name = st.text_input("Ім'я клієнта")
      client_phone = st.text_input("Телефон клієнта")

      st.subheader("2. Дані автомобіля")
      car_brand = st.text_input("Марка авто (наприклад, Toyota)")
      car_model = st.text_input("Модель авто (наприклад, Camry)")
      car_number = st.text_input(
          "Державний номер (наприклад, КА7777ВХ)"
      ).upper()
      car_year = st.number_input(
          "Рік випуску", min_value=1990, max_value=2026, value=2022
      )

      st.subheader("3. Вибір послуг")
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

      st.subheader("4. Матеріали та плівка")
      use_film = st.checkbox("Використовувати плівку зі складу", value=True)
      film_id = None
      meters_used = 0.0

      film_options = (
          {
              f"{row['film_name']} (Ширина: {row['width_cm']} см | Залишок: {row['meters_left']} м)": row[
                  "id"
              ]
              for _, row in inventory_df.iterrows()
          }
          if not inventory_df.empty
          else {}
      )

      if use_film and film_options:
        selected_film_label = st.selectbox(
            "Виберіть рулон/плівку", list(film_options.keys())
        )
        film_id = film_options[selected_film_label]
        meters_used = st.number_input(
            "Витрата плівки (пог. метрів)", min_value=0.1, value=1.5, step=0.1
        )

      supply_options = (
          {
              f"{r['item_name']} (Залишок: {r['quantity']} {r.get('unit','')})": r[
                  "id"
              ]
              for _, r in supplies_df_list.iterrows()
          }
          if not supplies_df_list.empty
          else {}
      )
      chosen_supply_id = None
      supply_used_qty = 0.0
      if supply_options:
        chosen_supply_label = st.selectbox(
            "Додатковий розхідник зі складу (опціонально)",
            ["Не використовувати"] + list(supply_options.keys()),
        )
        if chosen_supply_label != "Не використовувати":
          chosen_supply_id = supply_options[chosen_supply_label]
          supply_used_qty = st.number_input(
              "Кількість використаного розхідника",
              min_value=0.1,
              value=1.0,
              step=0.1,
          )

      total_price = st.number_input(
          "Попередня ціна для клієнта (грн)",
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

      master_percent = st.number_input(
          "Ставка майстра (%)", min_value=0.0, max_value=100.0, value=15.0, step=1.0
      )

      warranty_months = st.number_input(
          "Гарантія (місяців)", min_value=0, value=12, step=1
      )

      date = st.date_input("Дата візиту", value=datetime.now())
      time = st.time_input("Час візиту", value=datetime.now().time())

      submitted = st.form_submit_button("Створити запис")

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
        # Списання плівки
        if film_id and meters_used > 0:
          cursor.execute(
              "SELECT cost_per_meter_uah, meters_left FROM inventory WHERE id ="
              " ?",
              (film_id,),
          )
          f_row = cursor.fetchone()
          if f_row:
            cost_per_meter_uah, current_meters = f_row[0], f_row[1]
            cost_price += meters_used * cost_per_meter_uah

            if status in ["В роботі", "Виконано"]:
              new_meters = max(0.0, current_meters - meters_used)
              cursor.execute(
                  "UPDATE inventory SET meters_left = ? WHERE id = ?",
                  (new_meters, film_id),
              )

        # Списання розхідника
        if chosen_supply_id and supply_used_qty > 0:
          cursor.execute(
              "SELECT cost, quantity FROM supplies WHERE id = ?",
              (chosen_supply_id,),
          )
          s_res = cursor.fetchone()
          if s_res:
            s_cost_total, s_qty_total = s_res[0], s_res[1]
            if s_qty_total > 0:
              unit_cost = s_cost_total / s_qty_total
              cost_price += unit_cost * supply_used_qty
              if status in ["В роботі", "Виконано"]:
                new_s_qty = max(0.0, s_qty_total - supply_used_qty)
                cursor.execute(
                    "UPDATE supplies SET quantity = ? WHERE id = ?",
                    (new_s_qty, chosen_supply_id),
                )

        master_payout = total_price * (master_percent / 100.0)

        cursor.execute(
            """INSERT INTO appointments (client_id, car_id, film_id, meters_used, supply_id, supply_qty,
                   total_price, payment_type, cost_price, master_percent, master_payout, 
                   status, date, time, warranty_months, photo_path, comment) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                client_id,
                car_id,
                film_id,
                meters_used,
                chosen_supply_id,
                supply_used_qty,
                total_price,
                payment_type,
                cost_price,
                master_percent,
                master_payout,
                status,
                str(date),
                str(time),
                warranty_months,
                "",
                "",
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

        st.success("Запис успішно створено!")
        st.rerun()

  st.divider()
  st.subheader("📋 Список усіх записів")

  appointments_df = run_query("""
        SELECT a.id, cl.name as 'Клієнт', cl.phone as 'Телефон', 
               c.car_brand as 'Марка', c.car_model as 'Модель', c.car_number as 'Держномер', 
               a.total_price as 'Сума (грн)', a.cost_price as 'Собівартість', 
               a.master_payout as 'Зарплата майстра', a.master_percent,
               (a.total_price - a.cost_price - a.master_payout) as 'Чистий прибуток', 
               a.status as 'Статус', a.date as 'Дата', a.time as 'Час', 
               a.photo_path, a.comment, a.film_id, a.meters_used, a.supply_id, a.supply_qty
        FROM appointments a
        JOIN clients cl ON a.client_id = cl.id
        JOIN cars c ON a.car_id = c.id
        ORDER BY a.date DESC, a.time DESC
    """)

  if not appointments_df.empty:
    for _, row in appointments_df.iterrows():
      exp_label = (
          f"📅 {row['Дата']} {str(row['Час'])[:5]} | {row['Клієнт']} —"
          f" {row['Марка']} {row['Модель']} ({row['Держномер']}) | Статус:"
          f" {row['Статус']} | Сума: {row['Сума (грн)']} грн"
      )
      with st.expander(exp_label):
        st.write(
            f"💰 **Сума:** {row['Сума (грн]'} грн | 📦 **Собівартість:**"
            f" {row['Собівартість']:.1f} грн | 💵 **Майстру ({row['master_percent']}%):**"
            f" {row['Зарплата майстра']:.1f} грн | 📈 **Чистий прибуток:**"
            f" **{row['Чистий прибуток']:.1f} грн**"
        )
        if row["comment"]:
          st.info(f"📝 **Коментар/нюанси:** {row['comment']}")

        if (
            row["photo_path"]
            and isinstance(row["photo_path"], str)
            and os.path.exists(row["photo_path"])
        ):
          st.image(
              row["photo_path"],
              caption="Фотофіксація виконаної роботи",
              width=300,
          )

        with st.form(f"edit_app_{row['id']}"):
          st.subheader("Редагування / Закінчення робіт по авто")

          new_status = st.selectbox(
              "Змінити статус",
              ["Заплановано", "В роботі", "Виконано", "Скасовано"],
              index=[
                  "Заплановано",
                  "В роботі",
                  "Виконано",
                  "Скасовано",
              ].index(row["Статус"]),
          )
          final_price = st.number_input(
              "Фінальна ціна для клієнта (грн)",
              value=float(row["Сума (грн)"]),
              step=50.0,
          )
          new_master_percent = st.number_input(
              "Ставка майстра (%)",
              min_value=0.0,
              max_value=100.0,
              value=float(
                  row["master_percent"]
                  if pd.notna(row["master_percent"])
                  else 15.0
              ),
              step=1.0,
          )

          inventory_df_list = run_query(
              "SELECT id, film_name, width_cm, meters_left FROM inventory"
          )
          film_options = (
              {
                  f"{r['film_name']} (Ширина: {r['width_cm']} см | Залишок: {r['meters_left']} м)": r[
                      "id"
                  ]
                  for _, r in inventory_df_list.iterrows()
              }
              if not inventory_df_list.empty
              else {}
          )

          chosen_film_id = row["film_id"]
          film_used_qty = float(
              row["meters_used"] if pd.notna(row["meters_used"]) else 0.0
          )

          if film_options:
            film_keys = list(film_options.keys())
            default_film_idx = 0
            for idx, k in enumerate(film_keys):
              if film_options[k] == row["film_id"]:
                default_film_idx = idx + 1
                break

            chosen_film_label = st.selectbox(
                "Плівка зі складу", ["Не використовувати"] + film_keys, index=default_film_idx if default_film_idx < len(film_keys)+1 else 0
            )
            if chosen_film_label != "Не використовувати":
              chosen_film_id = film_options[chosen_film_label]
              film_used_qty = st.number_input(
                  "Витрата плівки (пог. метрів)",
                  min_value=0.1,
                  value=max(0.1, film_used_qty),
                  step=0.1,
              )
            else:
              chosen_film_id = None
              film_used_qty = 0.0

          supplies_df_list = run_query(
              "SELECT id, item_name, quantity, cost FROM supplies"
          )
          supply_options = (
              {
                  f"{r['item_name']} (Залишок: {r['quantity']})": r["id"]
                  for _, r in supplies_df_list.iterrows()
              }
              if not supplies_df_list.empty
              else {}
          )

          chosen_supply_id = row["supply_id"]
          supply_used_qty = float(
              row["supply_qty"] if pd.notna(row["supply_qty"]) else 0.0
          )

          if supply_options:
            sup_keys = list(supply_options.keys())
            default_sup_idx = 0
            for idx, k in enumerate(sup_keys):
              if supply_options[k] == row["supply_id"]:
                default_sup_idx = idx + 1
                break

            chosen_supply_label = st.selectbox(
                "Додатковий розхідник зі складу",
                ["Не використовувати"] + sup_keys,
                index=default_sup_idx if default_sup_idx < len(sup_keys)+1 else 0
            )
            if chosen_supply_label != "Не використовувати":
              chosen_supply_id = supply_options[chosen_supply_label]
              supply_used_qty = st.number_input(
                  "Кількість використаного розхідника",
                  min_value=0.1,
                  value=max(0.1, supply_used_qty),
                  step=0.1,
              )
            else:
              chosen_supply_id = None
              supply_used_qty = 0.0

          comment = st.text_area(
              "Коментар / Нюанси по авто",
              value=str(row["comment"] if row["comment"] else ""),
          )

          photo_file = None
          if new_status == "Виконано":
            photo_file = st.file_uploader(
                "📸 Фотофіксація авто (До / Після)",
                type=["jpg", "png", "jpeg"],
                key=f"ph_{row['id']}",
            )

          col_btn1, col_btn2 = st.columns(2)
          with col_btn1:
            update_btn = st.form_submit_button("💾 Зберегти зміни")
          with col_btn2:
            delete_app_btn = st.form_submit_button("🗑️ Видалити запис повністю")

          if update_btn:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()

            # Перерахунок собівартості з урахуванням нових списань
            base_cost = 0.0
            if chosen_film_id and film_used_qty > 0:
              cursor.execute(
                  "SELECT cost_per_meter_uah, meters_left FROM inventory WHERE id ="
                  " ?",
                  (chosen_film_id,),
              )
              f_res = cursor.fetchone()
              if f_res:
                c_meter, c_left = f_res[0], f_res[1]
                base_cost += film_used_qty * c_meter
                if new_status in ["В роботі", "Виконано"]:
                  new_meters = max(0.0, c_left - film_used_qty)
                  cursor.execute(
                      "UPDATE inventory SET meters_left = ? WHERE id = ?",
                      (new_meters, chosen_film_id),
                  )

            if chosen_supply_id and supply_used_qty > 0:
              cursor.execute(
                  "SELECT cost, quantity FROM supplies WHERE id = ?",
                  (chosen_supply_id,),
              )
              s_res = cursor.fetchone()
              if s_res:
                s_cost_total, s_qty_total = s_res[0], s_res[1]
                if s_qty_total > 0:
                  unit_cost = s_cost_total / s_qty_total
                  base_cost += unit_cost * supply_used_qty
                  if new_status in ["В роботі", "Виконано"]:
                    new_s_qty = max(0.0, s_qty_total - supply_used_qty)
                    cursor.execute(
                        "UPDATE supplies SET quantity = ? WHERE id = ?",
                        (new_s_qty, chosen_supply_id),
                    )

            new_master_payout = final_price * (new_master_percent / 100.0)

            photo_path = row["photo_path"]
            if photo_file is not None:
              os.makedirs("uploads", exist_ok=True)
              photo_path = f"uploads/{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo_file.name}"
              with open(photo_path, "wb") as f:
                f.write(photo_file.getbuffer())

            cursor.execute(
                """UPDATE appointments SET status = ?, total_price = ?, cost_price = ?, 
                       master_percent = ?, master_payout = ?, photo_path = ?, comment = ?, 
                       film_id = ?, meters_used = ?, supply_id = ?, supply_qty = ? 
                       WHERE id = ?""",
                (
                    new_status,
                    final_price,
                    base_cost,
                    new_master_percent,
                    new_master_payout,
                    photo_path,
                    comment,
                    chosen_film_id,
                    film_used_qty,
                    chosen_supply_id,
                    supply_used_qty,
                    row["id"],
                ),
            )
            conn.commit()
            conn.close()

            st.success("Запис успішно оновлено!")
            st.rerun()

          if delete_app_btn:
            run_query(
                "DELETE FROM appointments WHERE id = ?",
                (row["id"],),
                fetch=False,
            )
            st.warning("Запис повністю видалено!")
            st.rerun()
  else:
    st.info("Ще немає записів.")


# ==========================================
# 3. КЛІЄНТИ ТА АВТОМОБІЛІ
# ==========================================
elif menu == "👥 Клієнти та Авто":
  st.title("👥 База клієнтів, авто та збереження історії")

  search_q = st.text_input(
      "🔍 Шукати за іменем клієнта, номером телефону або держномером авто:"
  ).strip()

  if search_q:
    query_str = """
            SELECT DISTINCT cl.id, cl.name, cl.phone
            FROM clients cl
            LEFT JOIN cars c ON cl.id = c.client_id
            WHERE cl.name LIKE ? OR cl.phone LIKE ? OR c.car_number LIKE ?
        """
    param = f"%{search_q}%"
    clients_df = run_query(query_str, (param, param, param))
  else:
    clients_df = run_query("SELECT id, name, phone FROM clients")

  if not clients_df.empty:
    st.write(f"Знайдено клієнтів: **{len(clients_df)}**")
    for _, client in clients_df.iterrows():
      exp_title = f"👤 {client['name']} (Тел: {client['phone']})"
      with st.expander(exp_title):
        cars_df = run_query(
            """SELECT id, car_brand as 'Марка', car_model as 'Модель', car_number as 'Держномер', car_year as 'Рік' 
               FROM cars WHERE client_id = ?""",
            (client["id"],),
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
            f"💰 **Загалом залишено грошей у студії:** `{total_spent:,.0f} грн`"
        )
        st.write("🚗 **Автомобілі клієнта:**")

        if not cars_df.empty:
          for _, c_row in cars_df.iterrows():
            col_c1, col_c2 = st.columns([4, 1])
            with col_c1:
              st.write(
                  f"• **{c_row['Марка']} {c_row['Модель']}** | Держномер:"
                  f" `{c_row['Держномер']}` | Рік: {c_row['Рік']}"
              )
            with col_c2:
              if st.button("🗑️ Авто", key=f"del_car_{c_row['id']}"):
                run_query(
                    "DELETE FROM cars WHERE id = ?",
                    (c_row["id"],),
                    fetch=False,
                )
                st.warning("Автомобіль видалено!")
                st.rerun()

        st.divider()
        if st.button("🗑️ Видалити клієнта повністю", key=f"del_cl_{client['id']}"):
          conn = sqlite3.connect(DB_NAME)
          cursor = conn.cursor()
          # Каскадне видалення пов'язаних записів, авто тощо
          cursor.execute(
              "DELETE FROM appointments WHERE client_id = ?", (client["id"],)
          )
          cursor.execute("DELETE FROM cars WHERE client_id = ?", (client["id"],))
          cursor.execute("DELETE FROM clients WHERE id = ?", (client["id"],))
          conn.commit()
          conn.close()
          st.warning("Клієнта та всі його записи/авто повністю видалено!")
          st.rerun()
  else:
    st.info("Клієнтів за таким запитом не знайдено.")


# ==========================================
# 4. СКЛАД (ПЛІВКИ ТА РОЗХІДНИКИ)
# ==========================================
elif menu == "📦 Склад (Плівки та Розхідники)":
  st.title("📦 Загальний склад матеріалів та розхідників")

  tab_f, tab_s = st.tabs(["Rolls (Плівки)", "Supplies (Розхідні матеріали)"])

  with tab_f:
    with st.expander("➕ Додати рулон плівки на склад"):
      # Отримуємо історію назв плівок для автозаповнення/підказки
      existing_films = run_query("SELECT DISTINCT film_name FROM inventory")
      film_names_list = (
          existing_films["film_name"].tolist() if not existing_films.empty else []
      )

      with st.form("add_film_form"):
        st.write("Ви можете вибрати назву з попередніх або ввести нову:")
        
        # Створюємо поле для вибору або введення
        film_name = st.selectbox(
            "Назва плівки (автодоповнення)",
            options=["-- Ввести нову назву --"] + film_names_list,
        )
        custom_film_name = st.text_input(
            "Або введіть нову назву плівки (якщо обрано 'Ввести нову')", value=""
        )

        category = st.selectbox(
            "Категорія",
            [
                "Поліуретан (Бронеплівка)",
                "Тонувальна плівка",
                "Атермальна плівка",
            ],
        )

        col_w1, col_w2 = st.columns(2)
        with col_w1:
          preset_width = st.selectbox(
              "Ширина рулону (см)",
              options=[152.0, 102.0, 50.0, 75.0, 120.0, "Ввести свій розмір"],
          )
          if preset_width == "Ввести свій розмір":
            width_cm = st.number_input(
                "Вкажіть свою ширину рулону (см)",
                min_value=1.0,
                value=135.0,
                step=1.0,
            )
          else:
            width_cm = float(preset_width)

        with col_w2:
          meters_left = st.number_input(
              "Довжина рулону (пог. метрів)", min_value=0.1, value=30.0, step=1.0
          )

        st.write("💵 **Ціна за 1 метр (урахування курсу валют):**")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
          price_usd = st.number_input(
              "Ціна за 1 метр в ДОЛАРАХ ($)",
              min_value=0.0,
              value=15.0,
              step=0.5,
          )
        with col_c2:
          exchange_rate = st.number_input(
              "Поточний курс долара (грн)",
              min_value=1.0,
              value=41.5,
              step=0.1,
          )

        cost_per_meter_uah = price_usd * exchange_rate
        st.info(
            f"💡 Розрахункова собівартість 1 метра в гривнях:"
            f" **{cost_per_meter_uah:.2f} грн/м**"
        )

        min_limit = st.number_input(
            "Мінімальний залишок для попередження (м)",
            min_value=0.0,
            value=3.0,
            step=0.5,
        )

        submitted_film = st.form_submit_button("Додати плівку")
        
        final_f_name = (
            custom_film_name.strip()
            if film_name == "-- Ввести нову назву --"
            else film_name
        )

        if submitted_film and final_f_name:
          run_query(
              """INSERT INTO inventory (film_name, category, width_cm, meters_left, min_limit, price_usd, exchange_rate, cost_per_meter_uah) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (
                  final_f_name,
                  category,
                  width_cm,
                  meters_left,
                  min_limit,
                  price_usd,
                  exchange_rate,
                  cost_per_meter_uah,
              ),
              fetch=False,
          )
          st.success("Плівку успішно додано!")
          st.rerun()

    st.subheader("Рулони плівок на складі")
    inventory_df = run_query(
        """SELECT id, film_name as 'Назва', category as 'Категорія', 
                width_cm as 'Ширина (см)', meters_left as 'Залишок (м)', 
                price_usd as 'Ціна ($/м)', exchange_rate as 'Курс', 
                cost_per_meter_uah as 'Собівартість (грн/м)' 
         FROM inventory"""
    )
    if not inventory_df.empty:
      for _, row in inventory_df.iterrows():
        col_inv1, col_inv2 = st.columns([5, 1])
        with col_inv1:
          st.write(
              f"• **{row['Назва']}** | Категорія: {row['Категорія']} | Ширина:"
              f" {row['Ширина (см)']}см | Залишок: **{row['Залишок (м)']} м** |"
              f" Собівартість: {row['Собівартість (грн/м)']:.1f} грн/м"
          )
        with col_inv2:
          if st.button("🗑️ Видалити", key=f"del_inv_{row['id']}"):
            run_query(
                "DELETE FROM inventory WHERE id = ?",
                (row["id"],),
                fetch=False,
            )
            st.warning("Рулон плівки видалено зі складу!")
            st.rerun()
    else:
      st.info("Склад плівок порожній.")

  with tab_s:
    with st.expander("➕ Додати розхідний матеріал"):
      with st.form("add_supply_form"):
        item_name = st.text_input("Назва матеріалу (наприклад, Лезек, Ракель)")
        quantity = st.number_input("Кількість", min_value=0.0, value=10.0)
        unit = st.selectbox("Одиниця виміру", ["шт", "л", "упак", "м"])
        cost = st.number_input(
            "Загальна вартість покупки (грн)", min_value=0.0, value=500.0
        )

        sub_sup = st.form_submit_button("Додати розхідник")
        if sub_sup and item_name:
          run_query(
              "INSERT INTO supplies (item_name, quantity, unit, cost) VALUES"
              " (?, ?, ?, ?)",
              (item_name, quantity, unit, cost),
              fetch=False,
          )
          st.success("Розхідник додано!")
          st.rerun()

    st.subheader("Розхідні матеріали на складі")
    supplies_df = run_query(
        "SELECT id, item_name as 'Назва', quantity as 'Кількість', unit as"
        " 'Од.', cost as 'Вартість (грн)' FROM supplies"
    )
    if not supplies_df.empty:
      for _, row in supplies_df.iterrows():
        col_sup1, col_sup2 = st.columns([5, 1])
        with col_sup1:
          st.write(
              f"• **{row['Назва']}** — {row['Кількість']} {row['Од.']} (Загальна"
              f" вартість: {row['Вартість (грн)']} грн)"
          )
        with col_sup2:
          if st.button("🗑️ Видалити", key=f"del_sup_{row['id']}"):
            run_query(
                "DELETE FROM supplies WHERE id = ?",
                (row["id"],),
                fetch=False,
            )
            st.warning("Розхідник видалено зі складу!")
            st.rerun()
    else:
      st.info("Список розхідників порожній.")


# ==========================================
# 5. ЗАРПЛАТА МАЙСТРІВ
# ==========================================
elif menu == "💵 Зарплата майстрів":
  st.title("💵 Розрахунок зарплати майстрів")

  master_data = run_query("""
        SELECT a.date as 'Дата', c.car_brand || ' ' || c.car_model as 'Авто', 
               a.total_price as 'Сума замовлення', a.master_percent as 'Відсоток (%)', 
               a.master_payout as 'Виплата майстру (грн)', a.status as 'Статус'
        FROM appointments a
        JOIN cars c ON a.car_id = c.id
        WHERE a.status = 'Виконано'
        ORDER BY a.date DESC
    """)

  if not master_data.empty:
    total_salaries = master_data["Виплата майстру (грн)"].sum()
    st.metric(
        "💰 Загальна сума виплат майстрам (за виконані)",
        f"{total_salaries:,.0f} грн",
    )
    st.divider()
    st.subheader("Деталізація виплат")
    st.dataframe(master_data, use_container_width=True)
  else:
    st.info("Немає завершених замовлень для розрахунку зарплати.")


# ==========================================
# 6. ФІНАНСИ ТА ЗВІТИ
# ==========================================
elif menu == "💰 Фінанси та Звіти":
  st.title("💰 Фінансові звіти (Готівка vs Банківська карта)")

  cash_total_df = run_query(
      "SELECT SUM(total_price) as sum FROM appointments WHERE payment_type ='cash' AND status = 'Виконано'"
  )
  transfer_total_df = run_query(
      "SELECT SUM(total_price) as sum FROM appointments WHERE payment_type ='transfer' AND status = 'Виконано'"
  )

  cash_sum = (
      cash_total_df.iloc[0]["sum"]
      if not cash_total_df.empty and pd.notna(cash_total_df.iloc[0]["sum"])
      else 0.0
  )
  transfer_sum = (
      transfer_total_df.iloc[0]["sum"]
      if not transfer_total_df.empty
      and pd.notna(transfer_total_df.iloc[0]["sum"])
      else 0.0
  )

  col_f1, col_f2, col_f3 = st.columns(3)
  col_f1.metric("💵 Готівка (Каса)", f"{cash_sum:,.0f} грн")
  col_f2.metric("💳 Банківський переказ", f"{transfer_sum:,.0f} грн")
  col_f3.metric("💰 Загальний дохід", f"{cash_sum + transfer_sum:,.0f} грн")

  st.divider()

  fin_data = run_query("""
        SELECT a.date as 'Дата', cl.name as 'Клієнт', 
               c.car_brand || ' ' || c.car_model as 'Авто',
               a.total_price as 'Сума', a.cost_price as 'Собівартість матеріалу', 
               a.master_payout as 'Зарплата майстра',
               (a.total_price - a.cost_price - a.master_payout) as 'Чистий прибуток', 
               CASE WHEN a.payment_type = 'cash' THEN 'Готівка' ELSE 'Переказ' END as 'Тип оплати', 
               a.status as 'Статус'
        FROM appointments a
        JOIN clients cl ON a.client_id = cl.id
        JOIN cars c ON a.car_id = c.id
        WHERE a.status = 'Виконано'
        ORDER BY a.date DESC
    """)

  if not fin_data.empty:
    st.subheader("Детальна історія закритих замовлень з прибутками")
    st.dataframe(fin_data, use_container_width=True)
  else:
    st.info("Немає даних для фінансових звітів.")


# ==========================================
# 7. НАЛАШТУВАННЯ ПОСЛУГ
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
      with st.expander(
          f"✏️ {s_row['service_name']} — {s_row['default_price']} грн"
      ):
        with st.form(f"edit_srv_{s_row['id']}"):
          upd_name = st.text_input(
              "Назва послуги",
              value=s_row["service_name"],
              key=f"name_{s_row['id']}",
          )
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
                "UPDATE services SET service_name = ?, default_price = ? WHERE"
                " id = ?",
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
# 8. НАЛАШТУВАННЯ СИСТЕМИ
# ==========================================
elif menu == "⚙️ Налаштування системи":
  st.title("⚙️ Налаштування системи та безпеки даних")

  st.subheader("💾 Резервна копія бази даних")
  st.write(
      "Для гарантії того, що дані ніколи не втратяться при оновленні сервера,"
      " регулярно завантажуйте актуальний файл бази даних:"
  )

  if os.path.exists(DB_NAME):
    with open(DB_NAME, "rb") as f:
      st.download_button(
          label="📥 Завантажити резервну копію бази (.db)",
          data=f,
          file_name=f"tinting_crm_backup_{datetime.now().strftime('%Y%m%d')}.db",
          mime="application/octet-stream",
      )
  else:
    st.info("Файл бази даних ще не створено.")
