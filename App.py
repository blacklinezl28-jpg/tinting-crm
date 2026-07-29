from datetime import datetime, timezone, timedelta
import os
import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Detailing & Tinting CRM Pro", page_icon="🚗", layout="wide"
)

SYSTEM_PASSWORD = "123"

# Київський часовий пояс (UTC+3 або з урахуванням зимового/літнього часу)
KYIV_TZ = timezone(timedelta(hours=3))

def get_now_kyiv():
    return datetime.now(KYIV_TZ)


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

DB_NAME = "tinting_crm.db"


def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("PRAGMA foreign_keys = ON;")

  cursor.execute(
      "CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, service_name TEXT, default_price REAL)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, item_name TEXT, category TEXT, width_cm REAL,"
      " meters_left REAL, price_usd REAL, exchange_rate REAL,"
      " cost_per_unit_uah REAL, unit TEXT, min_limit REAL DEFAULT 5.0)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, client_name TEXT, client_phone TEXT, car_brand TEXT,"
      " car_model TEXT, car_number TEXT, created_at TEXT, date TEXT, time"
      " TEXT, status TEXT, final_price REAL, payment_type TEXT, material_cost"
      " REAL, net_profit REAL, comment TEXT)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS appointment_photos (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, appointment_id INTEGER, photo_type TEXT, photo_blob"
      " BLOB)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS appointment_services (appointment_id"
      " INTEGER, service_id INTEGER)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS appointment_inventory (id INTEGER PRIMARY"
      " KEY AUTOINCREMENT, appointment_id INTEGER, inventory_id INTEGER,"
      " qty_used REAL)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS inventory_log (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, date TEXT, item_name TEXT, car_info TEXT, qty_used REAL,"
      " unit TEXT, meters_left_after REAL)"
  )

  cursor.execute("PRAGMA table_info(appointments);")
  app_cols = [col[1] for col in cursor.fetchall()]
  if "created_at" not in app_cols:
    cursor.execute(
        "ALTER TABLE appointments ADD COLUMN created_at TEXT DEFAULT '';"
    )

  cursor.execute("PRAGMA table_info(inventory);")
  inv_cols = [col[1] for col in cursor.fetchall()]
  if "min_limit" not in inv_cols:
    cursor.execute("ALTER TABLE inventory ADD COLUMN min_limit REAL DEFAULT 5.0;")

  conn.commit()
  conn.close()


init_db()


def trigger_auto_backup():
  st.session_state["last_db_update"] = get_now_kyiv().strftime(
      "%Y-%m-%d %H:%M:%S"
  )


if "last_db_update" not in st.session_state:
  st.session_state["last_db_update"] = get_now_kyiv().strftime(
      "%Y-%m-%d %H:%M:%S"
  )


def run_query(query, params=(), fetch=True):
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()
  cursor.execute("PRAGMA foreign_keys = ON;")
  cursor.execute(query, params)
  if fetch:
    data = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    conn.close()
    return pd.DataFrame(data, columns=columns)
  else:
    conn.commit()
    conn.close()
    trigger_auto_backup()


if "selected_menu" not in st.session_state:
  st.session_state["selected_menu"] = "🏠 Головна (Огляд)"

st.sidebar.title("🚗 Меню CRM")
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Бекап та статус даних")
st.sidebar.info(
    f"🕒 Останнє збереження даних:\n**{st.session_state['last_db_update']}**"
)

if os.path.exists(DB_NAME):
  with open(DB_NAME, "rb") as f:
    st.sidebar.download_button(
        label="📥 Завантажити резервну копію бази",
        data=f,
        file_name="tinting_crm_backup.db",
        mime="application/octet-stream",
    )

menu_options = [
    "🏠 Головна (Огляд)",
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

today_str = get_now_kyiv().strftime("%Y-%m-%d")


def get_services_str(app_id):
  srv_ids = run_query(
      "SELECT service_id FROM appointment_services WHERE appointment_id = ?",
      (app_id,),
  )
  if not srv_ids.empty:
    all_s = run_query("SELECT * FROM services")
    if not all_s.empty:
      matched = all_s[all_s["id"].isin(srv_ids["service_id"])]
      if not matched.empty:
        return ", ".join(matched["service_name"].tolist())
  return "Не вказано"


if st.session_state["selected_menu"] == "🏠 Головна (Огляд)":
  st.header("🏠 Головна панель та Календар зайнятості")

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

  today_df = run_query(
      "SELECT SUM(final_price) as earned, SUM(net_profit) as profit FROM"
      " appointments WHERE status = 'Виконано' AND date = ?",
      (today_str,),
  )
  month_str = get_now_kyiv().strftime("%Y-%m")
  month_df = run_query(
      "SELECT SUM(final_price) as earned, SUM(net_profit) as profit FROM"
      " appointments WHERE status = 'Виконано' AND date LIKE ?",
      (f"{month_str}%",),
  )

  c1, c2 = st.columns(2)
  with c1:
    earned_today = (
        today_df["earned"].iloc[0]
        if not today_df.empty and pd.notna(today_df["earned"].iloc[0])
        else 0.0
    )
    profit_today = (
        today_df["profit"].iloc[0]
        if not today_df.empty and pd.notna(today_df["profit"].iloc[0])
        else 0.0
    )
    st.metric("💰 Заробіток за сьогодні", f"{earned_today:,.2f} грн")
    st.metric("📈 Прибуток за сьогодні", f"{profit_today:,.2f} грн")

  with c2:
    earned_month = (
        month_df["earned"].iloc[0]
        if not month_df.empty and pd.notna(month_df["earned"].iloc[0])
        else 0.0
    )
    profit_month = (
        month_df["profit"].iloc[0]
        if not month_df.empty and pd.notna(month_df["profit"].iloc[0])
        else 0.0
    )
    st.metric("💰 Заробіток за місяць", f"{earned_month:,.2f} грн")
    st.metric("📈 Прибуток за місяць", f"{profit_month:,.2f} грн")

  st.markdown("---")
  st.subheader("⏰ Найближчий запис")
  next_app = run_query(
      "SELECT * FROM appointments WHERE status = 'Очікує' ORDER BY date"
      " ASC, time ASC LIMIT 1"
  )
  if not next_app.empty:
    row = next_app.iloc[0]
    st.success(
        f"📅 **Дата виконання робіт:** {row['date']} о {row['time']}\n\n🚗"
        f" **Автомобіль:** {row['car_brand']} {row['car_model']}"
        f" ({row['car_number']})\n\n👤 **Клієнт:** {row['client_name']}"
        f" ({row['client_phone']})"
    )
    if st.button("👉 Редагувати запис / Змінити статус"):
      st.session_state["selected_menu"] = "📅 Записати клієнта / Записи"
      st.rerun()
  else:
    st.info("Наразі немає найближчих записів у статусі «Очікує».")

# 1. ЗАПИСАТИ КЛІЄНТА / ЗАПИСИ
elif st.session_state["selected_menu"] == "📅 Записати клієнта / Записи":
  st.header("📅 Журнал записів")
  tab1, tab2 = st.tabs(["Список активних записів", "➕ Записати клієнта"])

  with tab1:
    apps = run_query(
        "SELECT * FROM appointments WHERE status != 'Виконано' AND status !="
        " 'Скасовано' ORDER BY id DESC"
    )
    if not apps.empty:
      for idx, row in apps.iterrows():
        status_color = "🟡" if row["status"] == "Очікує" else "🔵"
        pay_info = (
            f"[{row['payment_type']}]" if pd.notna(row["payment_type"]) else ""
        )
        srv_ids = run_query(
            "SELECT service_id FROM appointment_services WHERE appointment_id"
            " = ?",
            (row["id"],),
        )
        matched_services = pd.DataFrame()
        services_text = "Не вказано"
        if not srv_ids.empty:
          all_s = run_query("SELECT * FROM services")
          if not all_s.empty:
            matched_services = all_s[all_s["id"].isin(srv_ids["service_id"])]
            if not matched_services.empty:
              services_text = ", ".join(
                  matched_services["service_name"].tolist()
              )

        with st.expander(
            f"{status_color} На виконання: {row['date']} {row['time']} |"
            f" {row['client_name']} ({row['car_brand']} {row['car_model']} -"
            f" {row['car_number']}) | Послуги: {services_text} | Статус:"
            f" {row['status']} {pay_info}"
        ):
          st.write(f"**Телефон:** {row['client_phone']}")
          st.write(
              f"**Створено:**"
              f" {row['created_at'] if pd.notna(row['created_at']) else 'Не вказано'}"
          )
          st.write(f"**Дата виконання робіт:** {row['date']} о {row['time']}")
          st.write(f"**Статус:** {row['status']}")
          st.write(f"**Замовлені послуги:** {services_text}")

          photos_df = run_query(
              "SELECT id, photo_type, photo_blob FROM appointment_photos WHERE"
              " appointment_id = ?",
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
              cur_date_obj = datetime.strptime(row["date"], "%Y-%m-%d").date()
            except:
              cur_date_obj = get_now_kyiv().date()
            
            try:
              cur_time_obj = datetime.strptime(row["time"], "%H:%M:%S").time()
            except:
              try:
                cur_time_obj = datetime.strptime(row["time"], "%H:%M").time()
              except:
                cur_time_obj = get_now_kyiv().time()

            new_work_date = st.date_input("Дата виконання робіт", value=cur_date_obj, key=f"upd_date_{row['id']}")
            new_work_time = st.time_input("Час виконання робіт", value=cur_time_obj, key=f"upd_time_{row['id']}")

            recommended_price = 0.0
            st.markdown("#### 🛠️ Послуги та вартість:")
            if not matched_services.empty:
              for _, s_row in matched_services.iterrows():
                st.write(
                    f"- {s_row['service_name']} — **{s_row['default_price']} грн**"
                )
                recommended_price += s_row["default_price"]
            else:
              st.write("Послуги не вибрані.")

            final_price = st.number_input(
                "Фінальна ціна за послуги (грн)",
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
                    value=0.0,
                    key=f"mat_qty_{row['id']}_{i}",
                )
              mat_rows_data.append((sel_mat, q_val, mat_options))

            if st.form_submit_button("➕ Додати ще один матеріал"):
              st.session_state[f"mat_count_{row['id']}"] += 1
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
              mat_cost = 0.0
              conn = sqlite3.connect(DB_NAME)
              cursor = conn.cursor()
              cursor.execute("PRAGMA foreign_keys = ON;")
              is_now_done = (
                  new_status == "Виконано" and row["status"] != "Виконано"
              )
              cursor.execute(
                  "DELETE FROM appointment_inventory WHERE appointment_id = ?",
                  (row["id"],),
              )
              car_info_str = (
                  f"{row['car_brand']} {row['car_model']} ({row['car_number']})"
              )

              for sel_mat, q_val, mat_options in mat_rows_data:
                m_id = mat_options[sel_mat]
                if m_id and q_val > 0:
                  cursor.execute(
                      "SELECT item_name, cost_per_unit_uah, meters_left, unit"
                      " FROM inventory WHERE id = ?",
                      (m_id,),
                  )
                  inv_res = cursor.fetchone()
                  if inv_res:
                    i_name_db, cost_per_unit, meters_left_db, unit_db = inv_res
                    mat_cost += cost_per_unit * q_val
                    cursor.execute(
                        """INSERT INTO appointment_inventory (appointment_id, inventory_id, qty_used) 
                                       VALUES (?, ?, ?)""",
                        (row["id"], m_id, q_val),
                    )
                    if is_now_done:
                      new_meters_left = meters_left_db - q_val
                      cursor.execute(
                          "UPDATE inventory SET meters_left = ? WHERE id = ?",
                          (new_meters_left, m_id),
                      )
                      cursor.execute(
                          """INSERT INTO inventory_log (date, item_name, car_info, qty_used, unit, meters_left_after) 
                                         VALUES (?, ?, ?, ?, ?, ?)""",
                          (
                              today_str,
                              i_name_db,
                              car_info_str,
                              q_val,
                              unit_db,
                              new_meters_left,
                          ),
                      )

              net_prof = final_price - mat_cost
              cursor.execute(
                  """UPDATE appointments SET status = ?, date = ?, time = ?, final_price = ?, payment_type = ?, 
                                         material_cost = ?, net_profit = ?, comment = ? 
                             WHERE id = ?""",
                  (
                      new_status,
                      str(new_work_date),
                      str(new_work_time),
                      final_price,
                      payment_type,
                      mat_cost,
                      net_prof,
                      comment,
                      row["id"],
                  ),
              )
              if ph_before_list:
                for file in ph_before_list:
                  cursor.execute(
                      """INSERT INTO appointment_photos (appointment_id, photo_type, photo_blob) 
                                     VALUES (?, 'before', ?)""",
                      (row["id"], file.getvalue()),
                  )
              if ph_after_list:
                for file in ph_after_list:
                  cursor.execute(
                      """INSERT INTO appointment_photos (appointment_id, photo_type, photo_blob) 
                                     VALUES (?, 'after', ?)""",
                      (row["id"], file.getvalue()),
                  )
              conn.commit()
              conn.close()
              trigger_auto_backup()
              st.success("✅ Зміни успішно збережено!")
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
            f"{s_row['service_name']} — {s_row['default_price']} грн",
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
      time = st.time_input("Час візиту", value=get_now_kyiv().time())
      comment = st.text_area("Початковий коментар")

      submit_app = st.form_submit_button("Записати клієнта")
      if submit_app:
        if c_name and car_brand:
          conn = sqlite3.connect(DB_NAME)
          cursor = conn.cursor()
          cursor.execute("PRAGMA foreign_keys = ON;")
          created_at_str = get_now_kyiv().strftime("%Y-%m-%d %H:%M:%S")
          cursor.execute(
              """INSERT INTO appointments (client_name, client_phone, car_brand, car_model, car_number, 
                                           created_at, date, time, status, final_price, material_cost, net_profit, comment) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Очікує', 0, 0, 0, ?)""",
              (
                  c_name,
                  c_phone,
                  car_brand,
                  car_model,
                  car_number,
                  created_at_str,
                  str(work_date),
                  str(time),
                  comment,
              ),
          )
          app_id = cursor.lastrowid
          if selected_services:
            for s_id_val in selected_services:
              cursor.execute(
                  "INSERT INTO appointment_services (appointment_id, service_id)"
                  " VALUES (?, ?)",
                  (app_id, s_id_val),
              )
          conn.commit()
          conn.close()
          trigger_auto_backup()
          st.success("✅ Авто успішно записано!")
        else:
          st.error("Введіть ім'я клієнта та марку автомобіля.")

# 2. СКЛАД
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
          st.markdown("💬 **Історія витрат (Вихід):**")
          log_df = run_query(
              "SELECT date, car_info, qty_used, unit, meters_left_after FROM"
              " inventory_log WHERE item_name = ? ORDER BY id DESC",
              (row["item_name"],),
          )
          if not log_df.empty:
            for _, l_row in log_df.iterrows():
              st.markdown(
                  f"- 📅 **{l_row['date']}** | 🚗 Авто: **{l_row['car_info']}** |"
                  f" Витрачено: **-{l_row['qty_used']} {l_row['unit']}** |"
                  f" Залишок: **{l_row['meters_left_after']} {l_row['unit']}**"
              )
          else:
            st.info("Ще не було витрат по цій позиції.")

          st.markdown("---")
          i_name = st.text_input(
              "Назва", value=row["item_name"], key=f"inv_n_{row['id']}"
          )
          i_cat = st.selectbox(
              "Категорія",
              ["Плівка", "Розхідник/Хімія"],
              index=0 if row["category"] == "Плівка" else 1,
              key=f"inv_c_{row['id']}",
          )
          i_width = st.number_input(
              "Ширина рулону (см)",
              value=(
                  float(row["width_cm"]) if pd.notna(row["width_cm"]) else 152.0
              ),
              key=f"inv_w_{row['id']}",
          )
          i_meters = st.number_input(
              "Залишок",
              value=float(row["meters_left"]),
              key=f"inv_m_{row['id']}",
          )
          i_min_limit = st.number_input(
              "Критичний ліміт попередження",
              value=float(row["min_limit"])
              if "min_limit" in row and pd.notna(row["min_limit"])
              else 5.0,
              key=f"inv_ml_{row['id']}",
          )
          i_p_usd = st.number_input(
              "Ціна за одиницю ($)",
              value=(
                  float(row["price_usd"]) if pd.notna(row["price_usd"]) else 0.0
              ),
              key=f"inv_pu_{row['id']}",
          )
          i_rate = st.number_input(
              "Курс долара (грн)",
              value=(
                  float(row["exchange_rate"])
                  if pd.notna(row["exchange_rate"])
                  else 41.0
              ),
              key=f"inv_r_{row['id']}",
          )
          i_unit = st.text_input(
              "Од. виміру", value=row["unit"], key=f"inv_u_{row['id']}"
          )

          col1, col2 = st.columns(2)
          with col1:
            if st.button("Зберегти зміни", key=f"upd_inv_{row['id']}"):
              cost_uah = i_p_usd * i_rate
              run_query(
                  "UPDATE inventory SET item_name = ?, category = ?, width_cm ="
                  " ?, meters_left = ?, min_limit = ?, price_usd = ?,"
                  " exchange_rate = ?, cost_per_unit_uah = ?, unit = ? WHERE id"
                  " = ?",
                  (
                      i_name,
                      i_cat,
                      i_width,
                      i_meters,
                      i_min_limit,
                      i_p_usd,
                      i_rate,
                      cost_uah,
                      i_unit,
                      row["id"],
                  ),
                  fetch=False,
              )
              st.success("✅ Зміни успішно збережено!")
              st.rerun()
          with col2:
            if st.button(
                "Видалити позицію", key=f"del_inv_{row['id']}", type="primary"
            ):
              run_query(
                  "DELETE FROM inventory WHERE id = ?",
                  (row["id"],),
                  fetch=False,
              )
              st.warning("Позицію видалено!")
              st.rerun()
    else:
      st.info("Склад порожній.")

  with tab2:
    with st.form("add_inventory_form", clear_on_submit=True):
      item_name = st.text_input("Назва (наприклад, LLumar ATR 15)")
      category = st.selectbox("Категорія", ["Плівка", "Розхідник/Хімія"])
      width_cm = st.number_input(
          "Ширина рулону (см, якщо плівка)", value=152.0
      )
      meters_left = st.number_input("Кількість (метрів або штук)", value=30.0)
      min_limit = st.number_input("Критичний ліміт попередження", value=5.0)
      price_usd = st.number_input("Ціна за одиницю в доларах ($)", value=15.0)
      exchange_rate = st.number_input("Курс долара до гривні", value=41.0)
      unit = st.text_input("Одиниця виміру (м або шт)", value="м")
      if st.form_submit_button("Додати на склад"):
        if item_name:
          cost_uah = price_usd * exchange_rate
          run_query(
              """INSERT INTO inventory (item_name, category, width_cm, meters_left, min_limit, 
                                           price_usd, exchange_rate, cost_per_unit_uah, unit) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (
                  item_name,
                  category,
                  width_cm,
                  meters_left,
                  min_limit,
                  price_usd,
                  exchange_rate,
                  cost_uah,
                  unit,
              ),
              fetch=False,
          )
          st.success("✅ Додано!")

# 3. ПОСЛУГИ
elif st.session_state["selected_menu"] == "🛠️ Послуги":
  st.header("🛠️ Каталог послуг")
  tab1, tab2 = st.tabs(["Список послуг", "Додати послугу"])
  with tab1:
    serv_df = run_query("SELECT * FROM services")
    if not serv_df.empty:
      for idx, row in serv_df.iterrows():
        with st.expander(f"{row['service_name']} — {row['default_price']} грн"):
          new_name = st.text_input(
              "Назва послуги", value=row["service_name"], key=f"s_name_{row['id']}"
          )
          new_price = st.number_input(
              "Ціна за замовчуванням (грн)",
              value=float(row["default_price"]),
              key=f"s_price_{row['id']}",
          )
          col1, col2 = st.columns(2)
          with col1:
            if st.button("Зберегти", key=f"save_s_{row['id']}"):
              run_query(
                  "UPDATE services SET service_name = ?, default_price = ? WHERE"
                  " id = ?",
                  (new_name, new_price, row["id"]),
                  fetch=False,
              )
              st.success("✅ Оновлено!")
              st.rerun()
          with col2:
            if st.button("Видалити", key=f"del_s_{row['id']}", type="primary"):
              run_query(
                  "DELETE FROM services WHERE id = ?",
                  (row["id"],),
                  fetch=False,
              )
              st.warning("Видалено!")
              st.rerun()
    else:
      st.info("Список послуг порожній.")

  with tab2:
    with st.form("add_service_form", clear_on_submit=True):
      s_name = st.text_input("Назва послуги")
      s_price = st.number_input("Ціна за замовчуванням (грн)", value=2500.0)
      if st.form_submit_button("Додати послугу"):
        if s_name:
          run_query(
              "INSERT INTO services (service_name, default_price) VALUES (?, ?)",
              (s_name, s_price),
              fetch=False,
          )
          st.success("✅ Додано!")

# 4. БАЗА КЛІЄНТІВ, БОРГИ ТА ЗВІТИ
elif st.session_state["selected_menu"] == "👥 База клієнтів, Борги та Звіти":
  st.header("👥 База клієнтів, Борги та Єдиний звіт")
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
          f" ({d_row['car_number']}) | **Борг:** **{d_row['final_price']} грн**"
      )
    st.markdown("---")

  tab_analytics, tab_all_table, tab_edit_all = st.tabs([
      "📊 Аналітика та фільтри",
      "📋 Загальна нумерована таблиця",
      "✏️ Редагувати / Видалити записи",
  ])

  with tab_analytics:
    st.subheader("🔍 Пошук та аналіз усіх записів")
    search_query = st.text_input(
        "Введіть ім'я клієнта, телефон, марку авто або держ. номер для пошуку"
    )
    if search_query:
      q = f"%{search_query}%"
      rep_df = run_query(
          """SELECT * FROM appointments 
                       WHERE client_name LIKE ? OR client_phone LIKE ? OR car_brand LIKE ? OR car_model LIKE ? OR car_number LIKE ? 
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
      selected_period = st.selectbox(
          "Фільтрувати фінансовий звіт за періодом", period_options
      )

      if selected_period != "За весь час":
        filtered_rep = rep_df[rep_df["Рік-Місяць"] == selected_period]
      else:
        filtered_rep = rep_df

      done_rep = filtered_rep[filtered_rep["status"] == "Виконано"]
      total_earned = done_rep["final_price"].sum()
      total_cost = done_rep["material_cost"].sum()
      total_net = done_rep["net_profit"].sum()
      total_cars = len(done_rep)

      col1, col2, col3, col4 = st.columns(4)
      col1.metric("Виконано авто", f"{total_cars} шт")
      col2.metric("Загальний дохід", f"{total_earned:,.2f} грн")
      col3.metric("Витрати на матеріали", f"{total_cost:,.2f} грн")
      col4.metric("Чистий прибуток", f"{total_net:,.2f} грн")

      st.markdown("---")
      st.subheader("📋 Деталі по записах")
      for _, f_row in filtered_rep.iterrows():
        srvs = get_services_str(f_row["id"])
        is_debt = "🔴 БОРГ" if f_row["payment_type"] == "Борг" else "🟢"
        with st.expander(
            f"{is_debt} Дата: {f_row['date']} | Клієнт: {f_row['client_name']} ({f_row['client_phone']}) | Авто: {f_row['car_brand']} {f_row['car_model']} ({f_row['car_number']}) | Послуги: {srvs} | Сума: {f_row['final_price']} грн [{f_row['status']}]"
        ):
          c_1, c_2 = st.columns(2)
          with c_1:
            st.write(f"**📅 Дата створення запису:** {f_row['created_at']}")
            st.write(f"**⏰ Дата та час виконання:** {f_row['date']} о {f_row['time']}")
            st.write(f"**👤 Клієнт:** {f_row['client_name']}")
            st.write(f"**📞 Телефон:** {f_row['client_phone']}")
            st.write(f"**🚗 Автомобіль:** {f_row['car_brand']} {f_row['car_model']} ({f_row['car_number']})")
          with c_2:
            st.write(f"**🛠️ Послуги:** {srvs}")
            st.write(f"**📌 Статус:** {f_row['status']}")
            st.write(f"**💳 Тип оплати:** {f_row['payment_type']}")
            st.write(f"**💰 Дохід:** {f_row['final_price']} грн | **Прибуток:** {f_row['net_profit']} грн")
            st.write(f"**💬 Коментар:** {f_row['comment'] if pd.notna(f_row['comment']) else 'Немає'}")

          p_df = run_query(
              "SELECT photo_type, photo_blob FROM appointment_photos WHERE appointment_id = ?",
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
        
        photos_chk = run_query("SELECT id FROM appointment_photos WHERE appointment_id = ?", (row["id"],))
        has_photos = "📸 Є фото" if not photos_chk.empty else "❌ Немає фото"
        
        display_rows.append({
            "№": index,
            "Дата візиту": f"{row['date']} {row['time']}",
            "Клієнт": row["client_name"],
            "Телефон": row["client_phone"],
            "Автомобіль": f"{row['car_brand']} {row['car_model']} ({row['car_number']})",
            "Послуги": srvs,
            "Статус": row["status"],
            "Сума (грн)": row["final_price"],
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
        with st.expander(
            f"{is_debt_mark} Виконання: {a_row['date']} | Клієнт:"
            f" {a_row['client_name']} | Послуги: {srvs} | Сума:"
            f" {a_row['final_price']} грн {p_type_label}"
        ):
          with st.form(f"admin_edit_app_{a_row['id']}"):
            ed_client = st.text_input(
                "Ім'я клієнта",
                value=str(a_row["client_name"]),
                key=f"ed_c_{a_row['id']}",
            )
            ed_phone = st.text_input(
                "Телефон",
                value=str(a_row["client_phone"]),
                key=f"ed_p_{a_row['id']}",
            )
            ed_brand = st.text_input(
                "Марка авто",
                value=str(a_row["car_brand"]),
                key=f"ed_b_{a_row['id']}",
            )
            ed_model = st.text_input(
                "Модель авто",
                value=str(a_row["car_model"]),
                key=f"ed_mo_{a_row['id']}",
            )
            ed_num = st.text_input(
                "Держ. номер",
                value=str(a_row["car_number"]),
                key=f"ed_n_{a_row['id']}",
            )
            
            st.markdown("#### 📅 Змінити дату та час візиту:")
            try:
              ed_date_obj = datetime.strptime(a_row["date"], "%Y-%m-%d").date()
            except:
              ed_date_obj = get_now_kyiv().date()
            try:
              ed_time_obj = datetime.strptime(a_row["time"], "%H:%M:%S").time()
            except:
              try:
                ed_time_obj = datetime.strptime(a_row["time"], "%H:%M").time()
              except:
                ed_time_obj = get_now_kyiv().time()

            ed_date = st.date_input("Дата виконання", value=ed_date_obj, key=f"ed_date_{a_row['id']}")
            ed_time = st.time_input("Час виконання", value=ed_time_obj, key=f"ed_time_{a_row['id']}")

            ed_price = st.number_input(
                "Фінальна ціна (грн)",
                value=float(a_row["final_price"])
                if pd.notna(a_row["final_price"])
                else 0.0,
                key=f"ed_pr_{a_row['id']}",
            )
            pay_opts = ["Готівка", "Банківська карта", "Борг"]
            cur_p = (
                a_row["payment_type"]
                if pd.notna(a_row["payment_type"])
                else "Готівка"
            )
            ed_pay = st.selectbox(
                "Тип оплати",
                pay_opts,
                index=pay_opts.index(cur_p) if cur_p in pay_opts else 0,
                key=f"ed_pay_{a_row['id']}",
            )
            status_opts = ["Очікує", "Виконано", "Скасовано"]
            cur_stat = a_row["status"]
            ed_status = st.selectbox(
                "Статус",
                status_opts,
                index=status_opts.index(cur_stat)
                if cur_stat in status_opts
                else 0,
                key=f"ed_stat_{a_row['id']}",
            )

            col_sub1, col_sub2 = st.columns(2)
            with col_sub1:
              save_btn = st.form_submit_button("💾 Зберегти зміни")
            with col_sub2:
              del_btn = st.form_submit_button(
                  "🗑️ Видалити цей запис", type="primary"
              )

            if save_btn:
              run_query(
                  """UPDATE appointments SET client_name = ?, client_phone = ?, car_brand = ?, 
                                         car_model = ?, car_number = ?, date = ?, time = ?, final_price = ?, 
                                         payment_type = ?, status = ? WHERE id = ?""",
                  (
                      ed_client,
                      ed_phone,
                      ed_brand,
                      ed_model,
                      ed_num,
                      str(ed_date),
                      str(ed_time),
                      ed_price,
                      ed_pay,
                      ed_status,
                      a_row["id"],
                  ),
                  fetch=False,
              )
              st.success("✅ Запис успішно оновлено!")
              st.rerun()

            if del_btn:
              run_query(
                  "DELETE FROM appointments WHERE id = ?",
                  (a_row["id"],),
                  fetch=False,
              )
              st.warning("⚠️ Запис видалено!")
              st.rerun()
    else:
      st.info("Архів записів порожній.")
