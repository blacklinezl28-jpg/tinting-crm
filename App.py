from datetime import datetime, timezone, timedelta, time as d_time
import os
import pandas as pd
import streamlit as st
import psycopg2
import psycopg2.extras

st.set_page_config(
    page_title="Detailing & Tinting CRM Pro", page_icon="🚗", layout="wide"
)

# Стиль для зміни кольору будь-якої кнопки при натисканні (активі, кліку)
st.markdown("""
    <style>
    div.stButton > button:active, div.stFormSubmitButton > button:active {
        background-color: #ff4b4b !important;
        color: white !important;
        border-color: #ff4b4b !important;
    }
    </style>
""", unsafe_allow_html=True)

# Київський часовий пояс
KYIV_TZ = timezone(timedelta(hours=3))

def get_now_kyiv():
    return datetime.now(KYIV_TZ)

# Підключення до Supabase PostgreSQL через Streamlit Secrets
@st.cache_resource
def init_connection():
    try:
        db_url = st.secrets["DATABASE_URL"]
        return psycopg2.connect(db_url, sslmode="require")
    except Exception as e:
        st.error(f"Помилка підключення до бази даних Supabase: {e}")
        return None

conn = init_connection()

def run_query(query, params=(), fetch=True):
    global conn
    try:
        # Перевірка з'єднання
        if conn is None or conn.closed != 0:
            conn = init_connection()
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
            conn.rollback()
        st.error(f"Помилка бази даних: {e}")
        return pd.DataFrame()

SYSTEM_PASSWORD = "blzl"


def check_password():
  if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
  if not st.session_state["authenticated"]:
    st.title("🔒 Авторизація в CRM-системі")
    entered_password = st.text_input("Пароль доступу", type="password")
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

def init_db():
    run_query("""
    CREATE TABLE IF NOT EXISTS services (
        id SERIAL PRIMARY KEY, 
        service_name TEXT, 
        default_price REAL
    );
    """, fetch=False)
    
    run_query("""
    CREATE TABLE IF NOT EXISTS inventory (
        id SERIAL PRIMARY KEY, 
        item_name TEXT, 
        category TEXT, 
        width_cm REAL,
        meters_left REAL, 
        price_usd REAL, 
        exchange_rate REAL,
        cost_per_unit_uah REAL, 
        unit TEXT, 
        min_limit REAL DEFAULT 5.0
    );
    """, fetch=False)
    
    run_query("""
    CREATE TABLE IF NOT EXISTS appointments (
        id SERIAL PRIMARY KEY, 
        client_name TEXT, 
        client_phone TEXT, 
        car_brand TEXT,
        car_model TEXT, 
        car_number TEXT, 
        created_at TEXT, 
        date TEXT, 
        time TEXT, 
        status TEXT, 
        final_price REAL, 
        payment_type TEXT, 
        material_cost REAL, 
        net_profit REAL, 
        comment TEXT
    );
    """, fetch=False)
    
    run_query("""
    CREATE TABLE IF NOT EXISTS appointment_photos (
        id SERIAL PRIMARY KEY, 
        appointment_id INTEGER, 
        photo_type TEXT, 
        photo_blob BYTEA
    );
    """, fetch=False)
    
    run_query("""
    CREATE TABLE IF NOT EXISTS appointment_services (
        appointment_id INTEGER, 
        service_id INTEGER
    );
    """, fetch=False)
    
    run_query("""
    CREATE TABLE IF NOT EXISTS appointment_inventory (
        id SERIAL PRIMARY KEY, 
        appointment_id INTEGER, 
        inventory_id INTEGER,
        qty_used REAL
    );
    """, fetch=False)
    
    run_query("""
    CREATE TABLE IF NOT EXISTS inventory_log (
        id SERIAL PRIMARY KEY, 
        date TEXT, 
        item_name TEXT, 
        car_info TEXT, 
        qty_used REAL,
        unit TEXT, 
        meters_left_after REAL
    );
    """, fetch=False)
    
    run_query("""
    CREATE TABLE IF NOT EXISTS appointment_spoiled (
        id SERIAL PRIMARY KEY, 
        appointment_id INTEGER, 
        inventory_id INTEGER,
        qty_spoiled REAL, 
        cost_uah REAL
    );
    """, fetch=False)

    # Таблиця для запам'ятовування середньої витрати плівки на модель авто
    run_query("""
    CREATE TABLE IF NOT EXISTS film_usage (
        id SERIAL PRIMARY KEY,
        car_model TEXT UNIQUE,
        avg_meters REAL
    );
    """, fetch=False)

init_db()

if "last_db_update" not in st.session_state:
  st.session_state["last_db_update"] = get_now_kyiv().strftime("%Y-%m-%d %H:%M:%S")

def trigger_auto_backup():
  st.session_state["last_db_update"] = get_now_kyiv().strftime("%Y-%m-%d %H:%M:%S")

if "selected_menu" not in st.session_state:
  st.session_state["selected_menu"] = "🏠 Інформаційна панель"

st.sidebar.title("🚗 Меню CRM")

menu_options = [
    "🏠 Інформаційна панель",
    "📅 Записати клієнта / Записи",
    "📦 Склад",
    "🛠️ Послуги",
    "👥 База клієнтів, Борги та Звіти",
]

current_index = (
    menu_options.index(st.session_state["selected_menu"])
    if st.session_state["selected_menu"] in menu_options
    else 0
)
selected_menu = st.sidebar.radio(
    "Виберіть розділ", menu_options, index=current_index
)
st.session_state["selected_menu"] = selected_menu

st.sidebar.markdown("---")
st.sidebar.subheader("💾 Статус даних (Supabase)")
st.sidebar.info(
    f"🕒 Останнє оновлення:\n**{st.session_state['last_db_update']}**"
)

today_str = get_now_kyiv().strftime("%Y-%m-%d")

def get_services_str(app_id):
  srv_ids = run_query(
      "SELECT service_id FROM appointment_services WHERE appointment_id = %s",
      (app_id,),
  )
  if not srv_ids.empty:
    all_s = run_query("SELECT * FROM services")
    if not all_s.empty:
      matched = all_s[all_s["id"].isin(srv_ids["service_id"])]
      if not matched.empty:
        return ", ".join(matched["service_name"].tolist())
  return "Не вказано"

def format_time_str(t_raw):
  if not t_raw:
    return ""
  try:
    if isinstance(t_raw, str):
      parts = t_raw.split(":")
      if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return str(t_raw)
  except:
    return str(t_raw)

# Функції для запам'ятовування плівки на авто
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

if st.session_state["selected_menu"] == "🏠 Інформаційна панель":
  st.header("🏠 Інформаційна панель")

  low_stock_df = run_query(
      "SELECT item_name, meters_left, min_limit, unit FROM inventory"
  )
  if not low_stock_df.empty:
    for _, l_row in low_stock_df.iterrows():
      m_left = float(l_row["meters_left"])
      m_lim = float(l_row["min_limit"])
      if m_left <= 0:
        st.error(
            f"🚨 УВАГА! Матеріал «{l_row['item_name']}» повністю закінчився!"
        )
      elif m_left <= m_lim:
        st.warning(
            f"⚠️ Кількість «{l_row['item_name']}» менша за критичний ліміт"
            f" ({m_left} {l_row['unit']})"
        )

  month_str = get_now_kyiv().strftime("%Y-%m")
  
  month_df = run_query(
      "SELECT SUM(final_price) as earned, SUM(net_profit) as profit, COUNT(*) as cars_count FROM"
      " appointments WHERE status = 'Виконано' AND date LIKE %s",
      (f"{month_str}%",),
  )

  month_spoiled_df = run_query(
      """SELECT SUM(s.cost_uah) as total_spoiled_cost 
         FROM appointment_spoiled s 
         JOIN appointments a ON s.appointment_id = a.id 
         WHERE a.date LIKE %s""",
      (f"{month_str}%",)
  )
  spoiled_month_cost = (
      month_spoiled_df["total_spoiled_cost"].iloc[0]
      if not month_spoiled_df.empty and pd.notna(month_spoiled_df["total_spoiled_cost"].iloc[0])
      else 0.0
  )

  total_queue_df = run_query(
      "SELECT COUNT(*) as total_queue FROM appointments WHERE status != 'Скасовано'"
  )
  total_queue_count = (
      total_queue_df["total_queue"].iloc[0]
      if not total_queue_df.empty and pd.notna(total_queue_df["total_queue"].iloc[0])
      else 0
  )

  earned_month = (
      month_df["earned"].iloc[0]
      if not month_df.empty and pd.notna(month_df["earned"].iloc[0])
      else 0.0
  )
  raw_profit_month = (
      month_df["profit"].iloc[0]
      if not month_df.empty and pd.notna(month_df["profit"].iloc[0])
      else 0.0
  )
  profit_month = raw_profit_month - spoiled_month_cost

  cars_month_count = (
      month_df["cars_count"].iloc[0]
      if not month_df.empty and pd.notna(month_df["cars_count"].iloc[0])
      else 0
  )

  m_col1, m_col2, m_col3 = st.columns(3)
  with m_col1:
    st.metric("💰 Каса за місяць", f"{int(earned_month):,} грн".replace(",", " "))
  with m_col2:
    st.metric("📈 Прибуток (з браком)", f"{int(profit_month):,} грн".replace(",", " "))
  with m_col3:
    st.metric("⚠️ Брак (у грошах)", f"{int(spoiled_month_cost):,} грн".replace(",", " "))

  m_col4, m_col5 = st.columns(2)
  with m_col4:
    st.metric("🚗 Виконано авто", f"{int(cars_month_count)} шт")
  with m_col5:
    st.metric("📌 Всього в черзі", f"{int(total_queue_count)} шт")

  st.markdown("---")
  st.subheader("⏰ Найближчий запис")
  next_app = run_query(
      "SELECT * FROM appointments WHERE status = 'Очікує' ORDER BY date"
      " ASC, time ASC LIMIT 1"
  )
  if not next_app.empty:
    row = next_app.iloc[0]
    formatted_time = format_time_str(row['time'])
    st.success(
        f"📅 **Дата виконання робіт:** {row['date']} о {formatted_time}\n\n🚗"
        f" **Автомобіль:** {row['car_brand']} {row['car_model']}"
        f" ({row['car_number']})\n\n👤 **Клієнт:** {row['client_name']}"
        f" ({row['client_phone']})"
    )
    if st.button("👉 Редагувати запис / Змінити статус"):
      st.session_state["selected_menu"] = "📅 Записати клієнта / Записи"
      st.rerun()
  else:
    st.info("Наразі немає найближчих записів у статусі «Очікує».")

  st.markdown("---")
  st.subheader("📅 Календар зайнятості")
  all_appointments_cal = run_query("SELECT date, status, car_brand, car_model, car_number, time FROM appointments ORDER BY date ASC, time ASC")
  
  if not all_appointments_cal.empty:
    unique_dates = all_appointments_cal["date"].unique()
    for d_val in unique_dates:
      day_apps = all_appointments_cal[all_appointments_cal["date"] == d_val]
      statuses = day_apps["status"].tolist()
      if "Очікує" in statuses:
        badge_color = "🟡"
      elif "Виконано" in statuses and "Очікує" not in statuses:
        badge_color = "🟢"
      else:
        badge_color = "🔴"

      with st.expander(f"{badge_color} Дата: {d_val} ({len(day_apps)} авто)"):
        for _, app_row in day_apps.iterrows():
          s_color = "🟡" if app_row["status"] == "Очікує" else ("🟢" if app_row["status"] == "Виконано" else "🔴")
          f_time = format_time_str(app_row['time'])
          st.markdown(
              f"- {s_color} **Час:** {f_time} | **Авто:** {app_row['car_brand']} {app_row['car_model']} ({app_row['car_number']}) | **Статус:** {app_row['status']}"
          )
  else:
    st.info("У календарі поки немає жодних записів.")

elif st.session_state["selected_menu"] == "📅 Записати клієнта / Записи":
  st.header("📅 Журнал записів")
  tab1, tab2 = st.tabs(["Список активних записів", "➕ Записати клієнта"])

  with tab1:
    apps = run_query(
        "SELECT * FROM appointments WHERE status != 'Виконано' AND status !="
        " 'Скасовано' ORDER BY date ASC, time ASC"
    )
    if not apps.empty:
      for idx, row in apps.iterrows():
        status_color = "🟡" if row["status"] == "Очікує" else "🔵"
        pay_info = (
            f"[{row['payment_type']}]" if pd.notna(row["payment_type"]) else ""
        )
        f_time_row = format_time_str(row['time'])
        srv_ids = run_query(
            "SELECT service_id FROM appointment_services WHERE appointment_id"
            " = %s",
            (row["id"],),
        )
        matched_services = pd.DataFrame()
        services_text = "Не вказано"
        assigned_service_ids = []
        if not srv_ids.empty:
          assigned_service_ids = srv_ids["service_id"].tolist()
        
        all_s = run_query("SELECT * FROM services")
        if assigned_service_ids and not all_s.empty:
          matched_services = all_s[all_s["id"].isin(assigned_service_ids)]
          if not matched_services.empty:
            services_text = ", ".join(matched_services["service_name"].tolist())

        with st.expander(
            f"{status_color} На виконання: {row['date']} {f_time_row} |"
            f" {row['client_name']} ({row['car_brand']} {row['car_model']} -"
            f" {row['car_number']}) | Послуги: {services_text} | Статус:"
            f" {row['status']} {pay_info}"
        ):
          st.write(f"**Телефон:** {row['client_phone']}")
          st.write(
              f"**Створено:**"
              f" {row['created_at'] if pd.notna(row['created_at']) else 'Не вказано'}"
          )
          st.write(f"**Дата виконання робіт:** {row['date']} о {f_time_row}")
          st.write(f"**Статус:** {row['status']}")
          st.write(f"**Замовлені послуги:** {services_text}")

          photos_df = run_query(
              "SELECT id, photo_type, photo_blob FROM appointment_photos WHERE"
              " appointment_id = %s",
              (row["id"],),
          )
          if not photos_df.empty:
            st.markdown("#### 📸 Збережені фотографії:")
            b_photos = photos_df[photos_df["photo_type"] == "before"]
            a_photos = photos_df[photos_df["photo_type"] == "after"]

            if not b_photos.empty:
              st.write("**Фото ДО:**")
              cols = st.columns(3)
              for i, (_, p_row) in enumerate(b_photos.iterrows()):
                with cols[i % 3]:
                  st.image(p_row["photo_blob"], use_column_width=True)

            if not a_photos.empty:
              st.write("**Фото ПІСЛЯ:**")
              cols = st.columns(3)
              for i, (_, p_row) in enumerate(a_photos.iterrows()):
                with cols[i % 3]:
                  st.image(p_row["photo_blob"], use_column_width=True)

          st.markdown("---")
          with st.form(f"update_app_form_{row['id']}"):
            new_status = st.selectbox(
                "Змінити статус",
                ["Очікує", "Виконано", "Скасовано"],
                index=[
                    "Очікує",
                    "Виконано",
                    "Скасовано",
                ].index(
                    row["status"] if row["status"] in ["Очікує", "Виконано", "Скасовано"] else "Очікує"
                ),
            )
            
            st.markdown("#### 📅 Змінити дату та час візиту:")
            try:
              cur_date_obj = datetime.strptime(str(row["date"]), "%Y-%m-%d").date()
            except:
              cur_date_obj = get_now_kyiv().date()
            
            try:
              cur_time_obj = datetime.strptime(str(row["time"]), "%H:%M:%S").time()
            except:
              try:
                cur_time_obj = datetime.strptime(str(row["time"]), "%H:%M").time()
              except:
                cur_time_obj = get_now_kyiv().time()

            new_work_date = st.date_input("Дата виконання робіт", value=cur_date_obj, key=f"upd_date_{row['id']}")
            new_work_time = st.time_input("Час виконання робіт (з 07:00 по 22:00)", value=cur_time_obj, key=f"upd_time_{row['id']}")

            st.markdown("#### 🛠️ Керування послугами:")
            updated_selected_services = []
            if not all_s.empty:
              for _, s_row in all_s.iterrows():
                is_checked = s_row["id"] in assigned_service_ids
                if st.checkbox(
                    f"{s_row['service_name']} — {int(s_row['default_price'])} грн",
                    value=is_checked,
                    key=f"upd_srv_{row['id']}_{s_row['id']}"
                ):
                  updated_selected_services.append(s_row["id"])
            else:
              st.info("Немає доступних послуг у каталозі.")

            recommended_price = 0.0
            if not all_s.empty and updated_selected_services:
              rec_df = all_s[all_s["id"].isin(updated_selected_services)]
              recommended_price = rec_df["default_price"].sum()

            final_price = st.number_input(
                "Фінальна ціна за послуги (грн)",
                min_value=0.0,
                step=50.0,
                value=(
                    float(row["final_price"])
                    if pd.notna(row["final_price"]) and row["final_price"] > 0
                    else float(recommended_price)
                ),
            )
            payment_types = ["Готівка", "Банківська карта", "Борг"]
            cur_pt = (
                row["payment_type"]
                if pd.notna(row["payment_type"])
                else "Готівка"
            )
            payment_type = st.selectbox(
                "Тип оплати",
                payment_types,
                index=(
                    payment_types.index(cur_pt) if cur_pt in payment_types else 0
                ),
            )

            inv_data = run_query("SELECT * FROM inventory")
            if f"mat_count_{row['id']}" not in st.session_state:
              st.session_state[f"mat_count_{row['id']}"] = 1

            # Автопідтягування рекомендованого метражу плівки для цього авто
            default_meters_auto = get_saved_film_meters(row['car_model'])

            st.markdown(
                "#### 🎞️🧴 Використані матеріали (Плівки та розхідники)"
            )
            mat_rows_data = []
            for i in range(st.session_state[f"mat_count_{row['id']}"]):
              c1, c2 = st.columns([3, 1])
              with c1:
                mat_options = {"Не вибрано": None}
                for _, i_row in inv_data.iterrows():
                  mat_options[
                      f"{i_row['item_name']} ({i_row['category']}) — залишок:"
                      f" {i_row['meters_left']} {i_row['unit']}"
                  ] = i_row["id"]
                sel_mat = st.selectbox(
                    f"Матеріал #{i+1}",
                    list(mat_options.keys()),
                    key=f"mat_sel_{row['id']}_{i}",
                )
              with c2:
                q_val = st.number_input(
                    f"Кількість #{i+1}",
                    min_value=0.0,
                    step=0.1,
                    value=float(default_meters_auto) if i == 0 else 1.0,
                    key=f"mat_qty_{row['id']}_{i}",
                )
              mat_rows_data.append((sel_mat, q_val, mat_options))

            if st.form_submit_button("➕ Додати ще один матеріал"):
              st.session_state[f"mat_count_{row['id']}"] += 1
              st.rerun()

            st.markdown("---")
            st.markdown("#### ❌ Облік браку матеріалів")
            if f"spoiled_count_{row['id']}" not in st.session_state:
              st.session_state[f"spoiled_count_{row['id']}"] = 1

            spoiled_rows_data = []
            for i in range(st.session_state[f"spoiled_count_{row['id']}"]):
              sc1, sc2 = st.columns([3, 1])
              with sc1:
                spoiled_options = {"Не вибрано": None}
                for _, i_row in inv_data.iterrows():
                  spoiled_options[
                      f"[Брак] {i_row['item_name']} ({i_row['category']}) — залишок:"
                      f" {i_row['meters_left']} {i_row['unit']}"
                  ] = i_row["id"]
                sel_spoiled_mat = st.selectbox(
                    f"Забракований матеріал #{i+1}",
                    list(spoiled_options.keys()),
                    key=f"spoiled_sel_{row['id']}_{i}",
                )
              with sc2:
                sq_val = st.number_input(
                    f"Кількість браку #{i+1}",
                    min_value=0.0,
                    step=0.1,
                    value=0.0,
                    key=f"spoiled_qty_{row['id']}_{i}",
                )
              spoiled_rows_data.append((sel_spoiled_mat, sq_val, spoiled_options))

            if st.form_submit_button("➕ Додати ще рядок браку"):
              st.session_state[f"spoiled_count_{row['id']}"] += 1
              st.rerun()

            comment = st.text_area(
                "Коментар / Нотатки",
                value=str(row["comment"]) if pd.notna(row["comment"]) else "",
            )

            st.markdown("---")
            st.markdown("#### 📸 Фотографії (До / Після)")
            ph_before_list = st.file_uploader(
                "Фото ДО виконання робіт",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key=f"ph_b_{row['id']}",
            )
            ph_after_list = st.file_uploader(
                "Фото ПІСЛЯ виконання робіт",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True,
                key=f"ph_a_{row['id']}",
            )

            submitted = st.form_submit_button("Зберегти зміни / Фініш")
            if submitted:
              if not (d_time(7, 0) <= new_work_time <= d_time(22, 0)):
                st.error("❌ Час виконання робіт має бути в межах з 07:00 по 22:00!")
              else:
                mat_cost = 0.0
                is_now_done = (new_status == "Виконано" and row["status"] != "Виконано")
                
                # Видаляємо старі зв'язки послуг та матеріалів перед оновленням
                run_query("DELETE FROM appointment_services WHERE appointment_id = %s", (row["id"],), fetch=False)
                for s_id_upd in updated_selected_services:
                  run_query("INSERT INTO appointment_services (appointment_id, service_id) VALUES (%s, %s)", (row["id"], s_id_upd), fetch=False)

                run_query("DELETE FROM appointment_inventory WHERE appointment_id = %s", (row["id"],), fetch=False)
                run_query("DELETE FROM appointment_spoiled WHERE appointment_id = %s", (row["id"],), fetch=False)
                
                car_info_str = f"{row['car_brand']} {row['car_model']} ({row['car_number']})"

                # Запам'ятовуємо метраж плівки для конкретної моделі авто
                for sel_mat, q_val, mat_options in mat_rows_data:
                  m_id = mat_options[sel_mat]
                  if m_id and q_val > 0:
                    inv_res = run_query("SELECT item_name, cost_per_unit_uah, meters_left, unit FROM inventory WHERE id = %s", (m_id,))
                    if not inv_res.empty:
                      i_name_db = inv_res.iloc[0]["item_name"]
                      cost_per_unit = float(inv_res.iloc[0]["cost_per_unit_uah"])
                      meters_left_db = float(inv_res.iloc[0]["meters_left"])
                      unit_db = inv_res.iloc[0]["unit"]
                      
                      mat_cost += cost_per_unit * q_val
                      run_query(
                          "INSERT INTO appointment_inventory (appointment_id, inventory_id, qty_used) VALUES (%s, %s, %s)",
                          (row["id"], m_id, q_val), fetch=False
                      )
                      
                      # Якщо вказували метри для плівки, зберігаємо для авто
                      save_film_meters(row['car_model'], q_val)

                      if is_now_done:
                        new_meters_left = round(meters_left_db - q_val, 2)
                        run_query("UPDATE inventory SET meters_left = %s WHERE id = %s", (new_meters_left, m_id), fetch=False)
                        run_query(
                            "INSERT INTO inventory_log (date, item_name, car_info, qty_used, unit, meters_left_after) VALUES (%s, %s, %s, %s, %s, %s)",
                            (today_str, i_name_db, car_info_str + " [Витрата]", q_val, unit_db, new_meters_left), fetch=False
                        )

                for sel_spoiled_mat, sq_val, spoiled_options in spoiled_rows_data:
                  sm_id = spoiled_options[sel_spoiled_mat]
                  if sm_id and sq_val > 0:
                    s_inv_res = run_query("SELECT item_name, cost_per_unit_uah, meters_left, unit FROM inventory WHERE id = %s", (sm_id,))
                    if not s_inv_res.empty:
                      s_i_name_db = s_inv_res.iloc[0]["item_name"]
                      s_cost_per_unit = float(s_inv_res.iloc[0]["cost_per_unit_uah"])
                      s_meters_left_db = float(s_inv_res.iloc[0]["meters_left"])
                      s_unit_db = s_inv_res.iloc[0]["unit"]
                      
                      spoiled_cost_item = s_cost_per_unit * sq_val
                      run_query(
                          "INSERT INTO appointment_spoiled (appointment_id, inventory_id, qty_spoiled, cost_uah) VALUES (%s, %s, %s, %s)",
                          (row["id"], sm_id, sq_val, spoiled_cost_item), fetch=False
                      )
                      if is_now_done:
                        new_s_meters_left = round(s_meters_left_db - sq_val, 2)
                        run_query("UPDATE inventory SET meters_left = %s WHERE id = %s", (new_s_meters_left, sm_id), fetch=False)
                        run_query(
                            "INSERT INTO inventory_log (date, item_name, car_info, qty_used, unit, meters_left_after) VALUES (%s, %s, %s, %s, %s, %s)",
                            (today_str, s_i_name_db, car_info_str + " [БРАК]", sq_val, s_unit_db, new_s_meters_left), fetch=False
                        )

                net_prof = final_price - mat_cost
                run_query(
                    """UPDATE appointments SET status = %s, date = %s, time = %s, final_price = %s, payment_type = %s, 
                                           material_cost = %s, net_profit = %s, comment = %s 
                               WHERE id = %s""",
                    (new_status, str(new_work_date), str(new_work_time), final_price, payment_type, mat_cost, net_prof, comment, row["id"]),
                    fetch=False,
                )
                
                if ph_before_list:
                  for file in ph_before_list:
                    run_query(
                        "INSERT INTO appointment_photos (appointment_id, photo_type, photo_blob) VALUES (%s, 'before', %s)",
                        (row["id"], psycopg2.Binary(file.getvalue())), fetch=False
                    )
                if ph_after_list:
                  for file in ph_after_list:
                    run_query(
                        "INSERT INTO appointment_photos (appointment_id, photo_type, photo_blob) VALUES (%s, 'after', %s)",
                        (row["id"], psycopg2.Binary(file.getvalue())), fetch=False
                    )
                
                trigger_auto_backup()
                st.success("✅ Зміни успішно збережено в Supabase!")
                st.rerun()
    else:
      st.info("Поки немає активних записів.")

  with tab2:
    st.subheader("Створити новий запис")
    services_df = run_query("SELECT * FROM services")
    st.markdown("### 🛠️ Виберіть послуги")
    selected_services = []
    if not services_df.empty:
      for _, s_row in services_df.iterrows():
        if st.checkbox(
            f"{s_row['service_name']} — {int(s_row['default_price'])} грн",
            key=f"srv_chk_{s_row['id']}",
        ):
          selected_services.append(s_row["id"])
    else:
      st.info("Спочатку додайте послуги у розділі «🛠️ Послуги».")

    with st.form("new_appointment_form", clear_on_submit=True):
      st.markdown("### 👤 Дані клієнта та авто")
      c_name = st.text_input("Ім'я та Прізвище клієнта")
      c_phone = st.text_input("Номер телефону")
      car_brand = st.text_input("Марка авто (наприклад, Toyota)")
      car_model = st.text_input("Модель (наприклад, Camry)")
      car_number = st.text_input("Держ. номер")
      st.markdown("### 📅 Дата та час виконання робіт")
      work_date = st.date_input("На коли записати автомобіль", value=get_now_kyiv().date())
      time = st.time_input("Час візиту (з 07:00 по 22:00)", value=get_now_kyiv().time())
      comment = st.text_area("Початковий коментар")

      submit_app = st.form_submit_button("Записати клієнта")
      if submit_app:
        if not (d_time(7, 0) <= time <= d_time(22, 0)):
          st.error("❌ Час виконання робіт має бути в межах з 07:00 по 22:00!")
        elif c_name and car_brand:
          created_at_str = get_now_kyiv().strftime("%Y-%m-%d %H:%M:%S")
          
          res_id = run_query(
              """INSERT INTO appointments (client_name, client_phone, car_brand, car_model, car_number, 
                                           created_at, date, time, status, final_price, material_cost, net_profit, comment) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Очікує', 0, 0, 0, %s) RETURNING id""",
              (c_name, c_phone, car_brand, car_model, car_number, created_at_str, str(work_date), str(time), comment)
          )
          if not res_id.empty:
            app_id = int(res_id.iloc[0]["id"])
            if selected_services:
              for s_id_val in selected_services:
                run_query(
                    "INSERT INTO appointment_services (appointment_id, service_id) VALUES (%s, %s)",
                    (app_id, s_id_val), fetch=False
                )
            trigger_auto_backup()
            st.success("✅ Авто успішно записано в хмару!")
        else:
          st.error("Введіть ім'я клієнта та марку автомобіля.")

elif st.session_state["selected_menu"] == "📦 Склад":
  st.header("📦 Облік складу (Плівки та Розхідники)")
  tab1, tab2 = st.tabs(["Залишки та Витрати", "Додати на склад"])
  with tab1:
    inv_df = run_query("SELECT * FROM inventory")
    if not inv_df.empty:
      for idx, row in inv_df.iterrows():
        width_info = (
            f" | Ширина: {row['width_cm']} см"
            if row["category"] == "Плівка"
            else ""
        )
        with st.expander(
            f"{row['item_name']} ({row['category']}){width_info} — Залишок:"
            f" {row['meters_left']} {row['unit']}"
        ):
          st.markdown("💬 **Історія витрат та браку:**")
          log_df = run_query(
              "SELECT date, car_info, qty_used, unit, meters_left_after FROM"
              " inventory_log WHERE item_name = %s ORDER BY id DESC",
              (row["item_name"],),
          )
          if not log_df.empty:
            for _, l_row in log_df.iterrows():
              st.markdown(
                  f"- 📅 **{l_row['date']}** | 🚗 Авто: **{l_row['car_info']}** |"
                  f" Кількість: **-{l_row['qty_used']} {l_row['unit']}** |"
                  f" Залишок: **{l_row['meters_left_after']} {l_row['unit']}**"
              )
          else:
            st.info("Ще не було витрат по цій позиції.")

          st.markdown("---")
          i_name = st.text_input("Назва", value=row["item_name"], key=f"inv_n_{row['id']}")
          i_cat = st.selectbox(
              "Категорія",
              ["Плівка", "Розхідник/Хімія"],
              index=0 if row["category"] == "Плівка" else 1,
              key=f"inv_c_{row['id']}",
          )
          
          i_width = float(row["width_cm"]) if pd.notna(row["width_cm"]) else 0.0
          if i_cat == "Плівка":
            i_width = st.number_input(
                "Ширина рулону (см)", step=0.1,
                value=i_width if i_width > 0 else 152.0,
                key=f"inv_w_{row['id']}",
            )
          else:
            i_width = 0.0

          i_meters = st.number_input(
              "Залишок", step=0.1,
              value=float(row["meters_left"]),
              key=f"inv_m_{row['id']}",
          )
          i_min_limit = st.number_input(
              "Критичний ліміт попередження", step=0.1,
              value=float(row["min_limit"]) if "min_limit" in row and pd.notna(row["min_limit"]) else 5.0,
              key=f"inv_ml_{row['id']}",
          )
          i_p_usd = st.number_input(
              "Ціна за одиницю ($)", step=0.5,
              value=float(row["price_usd"]) if pd.notna(row["price_usd"]) else 0.0,
              key=f"inv_pu_{row['id']}",
          )
          i_rate = st.number_input(
              "Курс долара (грн)", step=0.5,
              value=float(row["exchange_rate"]) if pd.notna(row["exchange_rate"]) else 41.0,
              key=f"inv_r_{row['id']}",
          )
          i_unit = st.text_input("Од. виміру", value=row["unit"], key=f"inv_u_{row['id']}")

          col1, col2 = st.columns(2)
          with col1:
            if st.button("Зберегти зміни", key=f"upd_inv_{row['id']}"):
              cost_uah = i_p_usd * i_rate
              run_query(
                  "UPDATE inventory SET item_name = %s, category = %s, width_cm = %s, meters_left = %s, min_limit = %s, price_usd = %s, exchange_rate = %s, cost_per_unit_uah = %s, unit = %s WHERE id = %s",
                  (i_name, i_cat, i_width, i_meters, i_min_limit, i_p_usd, i_rate, cost_uah, i_unit, row["id"]),
                  fetch=False,
              )
              st.success("✅ Зміни успішно збережено!")
              st.rerun()
          with col2:
            if st.button("Видалити позицію", key=f"del_inv_{row['id']}", type="primary"):
              run_query("DELETE FROM inventory WHERE id = %s", (row["id"],), fetch=False)
              st.warning("Позицію видалено!")
              st.rerun()
    else:
      st.info("Склад порожній.")

  with tab2:
    with st.form("add_inventory_form", clear_on_submit=True):
      item_name = st.text_input("Назва (наприклад, LLumar ATR 15 або Серветки)")
      category = st.selectbox("Категорія", ["Плівка", "Розхідник/Хімія"])
      
      width_cm = 0.0
      if category == "Плівка":
        width_cm = st.number_input("Ширина рулону (см)", step=0.1, value=152.0)

      meters_left = st.number_input("Кількість (метрів або штук)", step=0.1, value=30.0)
      min_limit = st.number_input("Критичний ліміт попередження", step=0.1, value=5.0)
      price_usd = st.number_input("Ціна за одиницю в доларах ($)", step=0.5, value=15.0)
      exchange_rate = st.number_input("Курс долара до гривні", step=0.5, value=41.0)
      unit = st.text_input("Одиниця виміру (м або шт)", value="м")
      if st.form_submit_button("Додати на склад"):
        if item_name:
          cost_uah = price_usd * exchange_rate
          run_query(
              """INSERT INTO inventory (item_name, category, width_cm, meters_left, min_limit, 
                                           price_usd, exchange_rate, cost_per_unit_uah, unit) 
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
              (item_name, category, width_cm, meters_left, min_limit, price_usd, exchange_rate, cost_uah, unit),
              fetch=False,
          )
          st.success("✅ Додано на склад у Supabase!")

elif st.session_state["selected_menu"] == "🛠️ Послуги":
  st.header("🛠️ Каталог послуг")
  tab1, tab2 = st.tabs(["Список послуг", "Додати послугу"])
  with tab1:
    serv_df = run_query("SELECT * FROM services")
    if not serv_df.empty:
      for idx, row in serv_df.iterrows():
        with st.expander(f"{row['service_name']} — {int(row['default_price'])} грн"):
          new_name = st.text_input("Назва послуги", value=row["service_name"], key=f"s_name_{row['id']}")
          new_price = st.number_input(
              "Ціна за замовчуванням (грн)", step=50.0,
              value=float(row["default_price"]),
              key=f"s_price_{row['id']}",
          )
          col1, col2 = st.columns(2)
          with col1:
            if st.button("Зберегти", key=f"save_s_{row['id']}"):
              run_query(
                  "UPDATE services SET service_name = %s, default_price = %s WHERE id = %s",
                  (new_name, new_price, row["id"]),
                  fetch=False,
              )
              st.success("✅ Оновлено!")
              st.rerun()
          with col2:
            if st.button("Видалити", key=f"del_s_{row['id']}", type="primary"):
              run_query("DELETE FROM services WHERE id = %s", (row["id"],), fetch=False)
              st.warning("Видалено!")
              st.rerun()
    else:
      st.info("Список послуг порожній.")

  with tab2:
    with st.form("add_service_form", clear_on_submit=True):
      s_name = st.text_input("Назва послуги")
      s_price = st.number_input("Ціна за замовчуванням (грн)", step=50.0, value=2500.0)
      if st.form_submit_button("Додати послугу"):
        if s_name:
          run_query(
              "INSERT INTO services (service_name, default_price) VALUES (%s, %s)",
              (s_name, s_price),
              fetch=False,
          )
          st.success("✅ Послугу додано!")

elif st.session_state["selected_menu"] == "👥 База клієнтів, Борги та Звіти":
  st.header("👥 База клієнтів, Картки та Звіти")
  debts_df = run_query(
      "SELECT id, client_name, client_phone, car_brand, car_model, car_number,"
      " final_price, date FROM appointments WHERE payment_type = 'Борг' AND"
      " status = 'Виконано'"
  )
  if not debts_df.empty:
    st.error("⚠️ УВАГА! Клієнти з невиплаченими боргами:")
    for _, d_row in debts_df.iterrows():
      st.markdown(
          f"🔴 **Клієнт:** {d_row['client_name']} ({d_row['client_phone']}) |"
          f" **Авто:** {d_row['car_brand']} {d_row['car_model']}"
          f" ({d_row['car_number']}) | **Борг:** **{int(d_row['final_price'])} грн**"
      )
    st.markdown("---")

  tab_clients, tab_analytics, tab_all_table, tab_edit_all = st.tabs([
      "👤 Картки клієнтів",
      "📊 Аналітика та фільтри",
      "📋 Загальна нумерована таблиця",
      "✏️ Редагувати / Видалити записи",
  ])

  with tab_clients:
    st.subheader("👤 База клієнтів та їхні автомобілі")
    client_search = st.text_input("Пошук клієнта за ім'ям або телефоном")
    
    if client_search:
      q_c = f"%{client_search}%"
      clients_list_df = run_query(
          "SELECT DISTINCT client_name, client_phone FROM appointments WHERE client_name LIKE %s OR client_phone LIKE %s",
          (q_c, q_c)
      )
    else:
      clients_list_df = run_query("SELECT DISTINCT client_name, client_phone FROM appointments")

    if not clients_list_df.empty:
      for _, c_row in clients_list_df.iterrows():
        c_name = c_row["client_name"]
        c_phone = c_row["client_phone"]

        client_spent_df = run_query(
            "SELECT SUM(final_price) as total_spent FROM appointments WHERE client_name = %s AND client_phone = %s AND status = 'Виконано'",
            (c_name, c_phone)
        )
        total_spent = (
            client_spent_df["total_spent"].iloc[0]
            if not client_spent_df.empty and pd.notna(client_spent_df["total_spent"].iloc[0])
            else 0.0
        )

        client_apps = run_query(
            "SELECT * FROM appointments WHERE client_name = %s AND client_phone = %s ORDER BY date DESC, time DESC",
            (c_name, c_phone)
        )

        with st.expander(f"👤 {c_name} ({c_phone}) — Всього приніс: {int(total_spent):,} грн".replace(",", " ")):
          st.markdown(f"**Телефон:** {c_phone}")
          st.markdown(f"**Загальна сума витрат клієнта:** **{int(total_spent):,} грн**".replace(",", " "))
          st.markdown("---")
          st.markdown(f"#### 🚗 Автомобілі та детальна історія обслуговування ({len(client_apps)} записів):")

          for _, a_item in client_apps.iterrows():
            srvs_text = get_services_str(a_item["id"])
            if a_item["status"] == "Очікує":
              st_icon = "🟡"
            elif a_item["status"] == "Виконано":
              st_icon = "🟢"
            else:
              st_icon = "🔴"
            f_time_item = format_time_str(a_item['time'])

            with st.expander(
                f"{st_icon} Дата: {a_item['date']} о {f_time_item} | Авто: {a_item['car_brand']} {a_item['car_model']} ({a_item['car_number']}) | Послуги: {srvs_text} | Сума: {int(a_item['final_price'])} грн [{a_item['status']}]"
            ):
              ac_1, ac_2 = st.columns(2)
              with ac_1:
                st.write(f"**📅 Дата створення запису:** {a_item['created_at']}")
                st.write(f"**⏰ Дата та час виконання:** {a_item['date']} о {f_time_item}")
                st.write(f"**👤 Клієнт:** {a_item['client_name']}")
                st.write(f"**📞 Телефон:** {a_item['client_phone']}")
                st.write(f"**🚗 Автомобіль:** {a_item['car_brand']} {a_item['car_model']} ({a_item['car_number']})")
              with ac_2:
                st.write(f"**🛠️ Послуги:** {srvs_text}")
                st.write(f"**📌 Статус:** {a_item['status']}")
                st.write(f"**💳 Тип оплати:** {a_item['payment_type']}")
                st.write(f"**💰 Дохід:** {int(a_item['final_price'])} грн | **Прибуток:** {int(a_item['net_profit'])} грн")
                st.write(f"**💬 Коментар:** {a_item['comment'] if pd.notna(a_item['comment']) else 'Немає'}")

              p_df = run_query(
                  "SELECT photo_type, photo_blob FROM appointment_photos WHERE appointment_id = %s",
                  (a_item["id"],),
              )
              if not p_df.empty:
                st.markdown("#### 📸 Завантажені фото (До / Після):")
                b_ph = p_df[p_df["photo_type"] == "before"]
                a_ph = p_df[p_df["photo_type"] == "after"]
                if not b_ph.empty:
                  st.write("**Фото ДО:**")
                  cols = st.columns(3)
                  for i, (_, pr) in enumerate(b_ph.iterrows()):
                    with cols[i % 3]:
                      st.image(pr["photo_blob"], use_column_width=True)
                if not a_ph.empty:
                  st.write("**Фото ПІСЛЯ:**")
                  cols = st.columns(3)
                  for i, (_, pr) in enumerate(a_ph.iterrows()):
                    with cols[i % 3]:
                      st.image(pr["photo_blob"], use_column_width=True)
    else:
      st.info("Клієнтів не знайдено.")

  with tab_analytics:
    st.subheader("🔍 Пошук та аналіз усіх записів")
    search_query = st.text_input("Введіть ім'я клієнта, телефон, марку авто або держ. номер для пошуку", key="search_analytics_input")
    if search_query:
      q = f"%{search_query}%"
      rep_df = run_query(
          """SELECT * FROM appointments 
                       WHERE client_name LIKE %s OR client_phone LIKE %s OR car_brand LIKE %s OR car_model LIKE %s OR car_number LIKE %s 
                       ORDER BY id DESC""",
          (q, q, q, q, q),
      )
    else:
      rep_df = run_query("SELECT * FROM appointments ORDER BY id DESC")

    if not rep_df.empty:
      rep_df["date_dt"] = pd.to_datetime(rep_df["date"], errors="coerce")
      rep_df["Рік-Місяць"] = rep_df["date_dt"].dt.strftime("%Y-%m")
      valid_months = rep_df["Рік-Місяць"].dropna().unique().tolist()
      period_options = ["За весь час"] + sorted(valid_months, reverse=True)
      selected_period = st.selectbox("Фільтрувати фінансовий звіт за періодом", period_options)

      if selected_period != "За весь час":
        filtered_rep = rep_df[rep_df["Рік-Місяць"] == selected_period]
      else:
        filtered_rep = rep_df

      done_rep = filtered_rep[filtered_rep["status"] == "Виконано"]
      total_earned = done_rep["final_price"].sum()
      total_cost = done_rep["material_cost"].sum()
      
      period_filter_sql_val = f"{selected_period}%" if selected_period != "За весь час" else "%"
      sp_rep_df = run_query(
          """SELECT SUM(s.cost_uah) as per_spoiled 
             FROM appointment_spoiled s 
             JOIN appointments a ON s.appointment_id = a.id 
             WHERE a.date LIKE %s""",
          (period_filter_sql_val,)
      )
      period_spoiled_cost = (
          sp_rep_df["per_spoiled"].iloc[0]
          if not sp_rep_df.empty and pd.notna(sp_rep_df["per_spoiled"].iloc[0])
          else 0.0
      )

      total_net = done_rep["net_profit"].sum() - period_spoiled_cost
      total_cars = len(done_rep)

      col_m1, col_m2 = st.columns(2)
      col_m1.metric("Виконано авто", f"{total_cars} шт")
      col_m2.metric("Загальний дохід", f"{int(total_earned):,} грн".replace(",", " "))

      col_m3, col_m4 = st.columns(2)
      col_m3.metric("Витрати на матеріали", f"{int(total_cost):,} грн".replace(",", " "))
      col_m4.metric("Чистий прибуток (з врахуванням браку)", f"{int(total_net):,} грн".replace(",", " "))

      st.markdown("---")
      st.subheader("📋 Деталі по записах")
      for _, f_row in filtered_rep.iterrows():
        srvs = get_services_str(f_row["id"])
        f_time_rep = format_time_str(f_row['time'])
        
        if f_row["status"] == "Очікує":
          status_icon = "🟡"
        elif f_row["status"] == "Виконано":
          status_icon = "🟢"
        else:
          status_icon = "🔴"

        is_debt = "🔴 БОРГ" if f_row["payment_type"] == "Борг" else status_icon
        with st.expander(
            f"{is_debt} Дата: {f_row['date']} | Клієнт: {f_row['client_name']} ({f_row['client_phone']}) | Авто: {f_row['car_brand']} {f_row['car_model']} ({f_row['car_number']}) | Послуги: {srvs} | Сума: {int(f_row['final_price'])} грн [{f_row['status']}]"
        ):
          c_1, c_2 = st.columns(2)
          with c_1:
            st.write(f"**📅 Дата створення запису:** {f_row['created_at']}")
            st.write(f"**⏰ Дата та час виконання:** {f_row['date']} о {f_time_rep}")
            st.write(f"**👤 Клієнт:** {f_row['client_name']}")
            st.write(f"**📞 Телефон:** {f_row['client_phone']}")
            st.write(f"**🚗 Автомобіль:** {f_row['car_brand']} {f_row['car_model']} ({f_row['car_number']})")
          with c_2:
            st.write(f"**🛠️ Послуги:** {srvs}")
            st.write(f"**📌 Статус:** {f_row['status']}")
            st.write(f"**💳 Тип оплати:** {f_row['payment_type']}")
            st.write(f"**💰 Дохід:** {int(f_row['final_price'])} грн | **Прибуток:** {int(f_row['net_profit'])} грн")
            st.write(f"**💬 Коментар:** {f_row['comment'] if pd.notna(f_row['comment']) else 'Немає'}")

          p_df = run_query(
              "SELECT photo_type, photo_blob FROM appointment_photos WHERE appointment_id = %s",
              (f_row["id"],),
          )
          if not p_df.empty:
            st.markdown("#### 📸 Завантажені фото (До / Після):")
            b_ph = p_df[p_df["photo_type"] == "before"]
            a_ph = p_df[p_df["photo_type"] == "after"]
            if not b_ph.empty:
              st.write("**Фото ДО:**")
              cols = st.columns(3)
              for i, (_, pr) in enumerate(b_ph.iterrows()):
                with cols[i % 3]:
                  st.image(pr["photo_blob"], use_column_width=True)
            if not a_ph.empty:
              st.write("**Фото ПІСЛЯ:**")
              cols = st.columns(3)
              for i, (_, pr) in enumerate(a_ph.iterrows()):
                with cols[i % 3]:
                  st.image(pr["photo_blob"], use_column_width=True)
    else:
      st.info("Нічого не знайдено.")

  with tab_all_table:
    st.subheader("📑 Загальна нумерована таблиця всіх записів")
    all_table_df = run_query("SELECT * FROM appointments ORDER BY id DESC")
    if not all_table_df.empty:
      display_rows = []
      for index, (_, row) in enumerate(all_table_df.iterrows(), start=1):
        srvs = get_services_str(row["id"])
        f_time_tbl = format_time_str(row['time'])
        
        photos_chk = run_query("SELECT id FROM appointment_photos WHERE appointment_id = %s", (row["id"],))
        has_photos = "📸 Є фото" if not photos_chk.empty else "❌ Немає фото"
        
        display_rows.append({
            "№": index,
            "Дата візиту": f"{row['date']} {f_time_tbl}",
            "Клієнт": row["client_name"],
            "Телефон": row["client_phone"],
            "Автомобіль": f"{row['car_brand']} {row['car_model']} ({row['car_number']})",
            "Послуги": srvs,
            "Статус": row["status"],
            "Сума (грн)": int(row["final_price"]) if pd.notna(row["final_price"]) else 0,
            "Оплата": row["payment_type"],
            "Фото": has_photos,
            "Коментар": row["comment"]
        })
      
      final_display_df = pd.DataFrame(display_rows)
      st.dataframe(final_display_df, use_container_width=True)
    else:
      st.info("База даних поки порожня.")

  with tab_edit_all:
    st.subheader("🛠️ Управління та редагування всіх записів")
    all_apps = run_query("SELECT * FROM appointments ORDER BY id DESC")
    if not all_apps.empty:
      for _, a_row in all_apps.iterrows():
        p_type_label = (
            f"[{a_row['payment_type']}]"
            if pd.notna(a_row["payment_type"])
            else "[Не вказано]"
        )
        is_debt_mark = "🔴 БОРГ" if a_row["payment_type"] == "Борг" else "🟢"
        srvs = get_services_str(a_row["id"])
        f_time_ed = format_time_str(a_row['time'])
        with st.expander(
            f"{is_debt_mark} Виконання: {a_row['date']} {f_time_ed} | Клієнт:"
            f" {a_row['client_name']} | Послуги: {srvs} | Сума:"
            f" {int(a_row['final_price'])} грн {p_type_label}"
        ):
          with st.form(f"admin_edit_app_{a_row['id']}"):
            ed_client = st.text_input("Ім'я клієнта", value=str(a_row["client_name"]), key=f"ed_c_{a_row['id']}")
            ed_phone = st.text_input("Телефон", value=str(a_row["client_phone"]), key=f"ed_p_{a_row['id']}")
            ed_brand = st.text_input("Марка авто", value=str(a_row["car_brand"]), key=f"ed_b_{a_row['id']}")
            ed_model = st.text_input("Модель авто", value=str(a_row["car_model"]), key=f"ed_mo_{a_row['id']}")
            ed_num = st.text_input("Держ. номер", value=str(a_row["car_number"]), key=f"ed_n_{a_row['id']}")
            
            st.markdown("#### 📅 Змінити дату та час візиту:")
            try:
              ed_date_obj = datetime.strptime(str(a_row["date"]), "%Y-%m-%d").date()
            except:
              ed_date_obj = get_now_kyiv().date()
            try:
              ed_time_obj = datetime.strptime(str(a_row["time"]), "%H:%M:%S").time()
            except:
              try:
                ed_time_obj = datetime.strptime(str(a_row["time"]), "%H:%M").time()
              except:
                ed_time_obj = get_now_kyiv().time()

            ed_date = st.date_input("Дата виконання", value=ed_date_obj, key=f"ed_date_{a_row['id']}")
            ed_time = st.time_input("Час виконання (з 07:00 по 22:00)", value=ed_time_obj, key=f"ed_time_{a_row['id']}")

            ed_price = st.number_input(
                "Фінальна ціна (грн)", min_value=0.0, step=50.0,
                value=float(a_row["final_price"]) if pd.notna(a_row["final_price"]) else 0.0,
                key=f"ed_pr_{a_row['id']}",
            )
            pay_opts = ["Готівка", "Банківська карта", "Борг"]
            cur_p = a_row["payment_type"] if pd.notna(a_row["payment_type"]) else "Готівка"
            ed_pay = st.selectbox(
                "Тип оплати", pay_opts,
                index=pay_opts.index(cur_p) if cur_p in pay_opts else 0,
                key=f"ed_pay_{a_row['id']}",
            )
            status_opts = ["Очікує", "Виконано", "Скасовано"]
            cur_stat = a_row["status"]
            ed_status = st.selectbox(
                "Статус", status_opts,
                index=status_opts.index(cur_stat) if cur_stat in status_opts else 0,
                key=f"ed_stat_{a_row['id']}",
            )

            col_sub1, col_sub2 = st.columns(2)
            with col_sub1:
              save_btn = st.form_submit_button("💾 Зберегти зміни")
            with col_sub2:
              del_btn = st.form_submit_button("🗑️ Видалити цей запис", type="primary")

            if save_btn:
              if not (d_time(7, 0) <= ed_time <= d_time(22, 0)):
                st.error("❌ Час виконання робіт має бути в межах з 07:00 по 22:00!")
              else:
                run_query(
                    """UPDATE appointments SET client_name = %s, client_phone = %s, car_brand = %s, 
                                           car_model = %s, car_number = %s, date = %s, time = %s, final_price = %s, 
                                           payment_type = %s, status = %s WHERE id = %s""",
                    (ed_client, ed_phone, ed_brand, ed_model, ed_num, str(ed_date), str(ed_time), ed_price, ed_pay, ed_status, a_row["id"]),
                    fetch=False,
                )
                st.success("✅ Запис успішно оновлено!")
                st.rerun()

            if del_btn:
              run_query("DELETE FROM appointments WHERE id = %s", (a_row["id"],), fetch=False)
              st.warning("⚠️ Запис видалено!")
              st.rerun()
    else:
      st.info("Архів записів порожній.")
