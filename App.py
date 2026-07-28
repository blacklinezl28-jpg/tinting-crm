from datetime import datetime
import os
import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Detailing & Tinting CRM Pro", page_icon="🚗", layout="wide"
)

SYSTEM_PASSWORD = "123"


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
      " cost_per_unit_uah REAL, unit TEXT)"
  )
  # Оновлена таблиця записів (з підтримкою 2 плівок та 2 розхідників)
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, client_name TEXT, client_phone TEXT, car_brand TEXT,"
      " car_model TEXT, car_number TEXT, date TEXT, time TEXT, status TEXT,"
      " final_price REAL, payment_type TEXT, film_id_1 INTEGER, film_meters_1"
      " REAL, film_id_2 INTEGER, film_meters_2 REAL, supply_id_1 INTEGER,"
      " supply_qty_1 REAL, supply_id_2 INTEGER, supply_qty_2 REAL,"
      " material_cost REAL, net_profit REAL, comment TEXT)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS appointment_services (appointment_id"
      " INTEGER, service_id INTEGER)"
  )
  conn.commit()
  conn.close()


init_db()


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


# МЕНЮ
st.sidebar.title("🚗 Меню CRM")
menu = st.sidebar.selectbox(
    "Виберіть розділ", [
        "🏠 Головна (Огляд)",
        "📅 Записати клієнта / Записи",
        "📦 Склад",
        "🛠️ Послуги",
        "👥 База клієнтів та Борги",
        "📊 Звіти та Аналітика",
    ]
)

today_str = datetime.now().strftime("%Y-%m-%d")

# ГОЛОВНА СТОРІНКА
if menu == "🏠 Головна (Огляд)":
  st.header("🏠 Головна панель")

  today_df = run_query(
      "SELECT SUM(final_price) as earned, SUM(net_profit) as profit FROM"
      " appointments WHERE status = 'Виконано' AND date = ?",
      (today_str,),
  )
  month_str = datetime.now().strftime("%Y-%m")
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
      "SELECT * FROM appointments WHERE status = 'Заплановано' ORDER BY date"
      " ASC, time ASC LIMIT 1"
  )
  if not next_app.empty:
    row = next_app.iloc[0]
    st.success(
        f"📅 **Дата/Час:** {row['date']} о {row['time']}\n\n🚗 **Автомобіль:"
        f"** {row['car_brand']} {row['car_model']} ({row['car_number']})\n\n👤"
        f" **Клієнт:** {row['client_name']} ({row['client_phone']})"
    )
  else:
    st.info("Наразі немає запланованих записів.")

# 1. ЗАПИСАТИ КЛІЄНТА / ЗАПИСИ
elif menu == "📅 Записати клієнта / Записи":
  st.header("📅 Журнал записів")
  tab1, tab2 = st.tabs(["Список записів", "➕ Записати клієнта"])

  with tab1:
    # Показуємо тільки активні запити (Заплановано або В роботі)
    apps = run_query(
        "SELECT * FROM appointments WHERE status != 'Виконано' ORDER BY date"
        " DESC"
    )
    if not apps.empty:
      for idx, row in apps.iterrows():
        status_color = "🟡" if row["status"] == "В роботі" else "🔵"
        pay_info = (
            f"[{row['payment_type']}]" if pd.notna(row["payment_type"]) else ""
        )
        with st.expander(
            f"{status_color} {row['date']} {row['time']} | {row['client_name']}"
            f" ({row['car_brand']} {row['car_model']} - {row['car_number']}) |"
            f" Статус: {row['status']} {pay_info}"
        ):
          st.write(f"**Телефон:** {row['client_phone']}")
          st.write(f"**Статус:** {row['status']}")

          srv_ids = run_query(
              "SELECT service_id FROM appointment_services WHERE appointment_id"
              " = ?",
              (row["id"],),
          )
          if not srv_ids.empty:
            all_s = run_query("SELECT * FROM services")
            matched_services = all_s[all_s["id"].isin(srv_ids["service_id"])]
            st.write(
                "**Послуги:**"
                f" {', '.join(matched_services['service_name'].tolist())}"
            )

          st.markdown("---")
          with st.form(f"update_app_form_{row['id']}"):
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

            final_price = st.number_input(
                "Фінальна ціна за послуги (грн)",
                value=(
                    float(row["final_price"])
                    if pd.notna(row["final_price"])
                    else 3000.0
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
            films = inv_data[inv_data["category"] == "Плівка"]
            supplies = inv_data[inv_data["category"] != "Плівка"]

            film_options = {"Не вибрано": None}
            for _, f_row in films.iterrows():
              film_options[
                  f"{f_row['item_name']} (Ширина: {f_row['width_cm']}см,"
                  f" залишок: {f_row['meters_left']}м)"
              ] = f_row["id"]

            st.markdown("#### 🎞️ Використані плівки")
            f1_col, f2_col = st.columns(2)
            with f1_col:
              sel_f1 = st.selectbox(
                  "Плівка 1", list(film_options.keys()), key=f"f1_{row['id']}"
              )
              m1 = st.number_input(
                  "Метраж плівки 1",
                  value=(
                      float(row["film_meters_1"])
                      if pd.notna(row.get("film_meters_1"))
                      else 0.0
                  ),
                  key=f"m1_{row['id']}",
              )
            with f2_col:
              sel_f2 = st.selectbox(
                  "Плівка 2 (якщо є)",
                  list(film_options.keys()),
                  key=f"f2_{row['id']}",
              )
              m2 = st.number_input(
                  "Метраж плівки 2",
                  value=(
                      float(row["film_meters_2"])
                      if pd.notna(row.get("film_meters_2"))
                      else 0.0
                  ),
                  key=f"m2_{row['id']}",
              )

            supp_options = {"Не вибрано": None}
            for _, s_row in supplies.iterrows():
              supp_options[
                  f"{s_row['item_name']} (залишок: {s_row['meters_left']}"
                  f" {s_row['unit']})"
              ] = s_row["id"]

            st.markdown("#### 🧴 Використані розхідники")
            s1_col, s2_col = st.columns(2)
            with s1_col:
              sel_s1 = st.selectbox(
                  "Розхідник 1",
                  list(supp_options.keys()),
                  key=f"s1_{row['id']}",
              )
              q1 = st.number_input(
                  "Кількість розхідника 1",
                  value=(
                      float(row["supply_qty_1"])
                      if pd.notna(row.get("supply_qty_1"))
                      else 0.0
                  ),
                  key=f"q1_{row['id']}",
              )
            with s2_col:
              sel_s2 = st.selectbox(
                  "Розхідник 2 (якщо є)",
                  list(supp_options.keys()),
                  key=f"s2_{row['id']}",
              )
              q2 = st.number_input(
                  "Кількість розхідника 2",
                  value=(
                      float(row["supply_qty_2"])
                      if pd.notna(row.get("supply_qty_2"))
                      else 0.0
                  ),
                  key=f"q2_{row['id']}",
              )

            comment = st.text_area(
                "Коментар / Нотатки",
                value=str(row["comment"]) if pd.notna(row["comment"]) else "",
            )

            submitted = st.form_submit_button("Зберегти зміни / Фініш")
            if submitted:
              f_id_1 = film_options[sel_f1]
              f_id_2 = film_options[sel_f2]
              s_id_1 = supp_options[sel_s1]
              s_id_2 = supp_options[sel_s2]

              mat_cost = 0.0
              conn = sqlite3.connect(DB_NAME)
              cursor = conn.cursor()

              is_now_done = (
                  new_status == "Виконано" and row["status"] != "Виконано"
              )

              # Розрахунок Плівки 1
              if f_id_1 and m1 > 0:
                cursor.execute(
                    "SELECT cost_per_unit_uah FROM inventory WHERE id = ?",
                    (f_id_1,),
                )
                res = cursor.fetchone()
                if res:
                  mat_cost += res[0] * m1
                  if is_now_done:
                    cursor.execute(
                        "UPDATE inventory SET meters_left = meters_left - ? WHERE"
                        " id = ?",
                        (m1, f_id_1),
                    )

              # Розрахунок Плівки 2
              if f_id_2 and m2 > 0:
                cursor.execute(
                    "SELECT cost_per_unit_uah FROM inventory WHERE id = ?",
                    (f_id_2,),
                )
                res = cursor.fetchone()
                if res:
                  mat_cost += res[0] * m2
                  if is_now_done:
                    cursor.execute(
                        "UPDATE inventory SET meters_left = meters_left - ? WHERE"
                        " id = ?",
                        (m2, f_id_2),
                    )

              # Розрахунок Розхідника 1
              if s_id_1 and q1 > 0:
                cursor.execute(
                    "SELECT cost_per_unit_uah FROM inventory WHERE id = ?",
                    (s_id_1,),
                )
                res = cursor.fetchone()
                if res:
                  mat_cost += res[0] * q1
                  if is_now_done:
                    cursor.execute(
                        "UPDATE inventory SET meters_left = meters_left - ? WHERE"
                        " id = ?",
                        (q1, s_id_1),
                    )

              # Розрахунок Розхідника 2
              if s_id_2 and q2 > 0:
                cursor.execute(
                    "SELECT cost_per_unit_uah FROM inventory WHERE id = ?",
                    (s_id_2,),
                )
                res = cursor.fetchone()
                if res:
                  mat_cost += res[0] * q2
                  if is_now_done:
                    cursor.execute(
                        "UPDATE inventory SET meters_left = meters_left - ? WHERE"
                        " id = ?",
                        (q2, s_id_2),
                    )

              net_prof = final_price - mat_cost

              cursor.execute(
                  """UPDATE appointments SET status = ?, final_price = ?, payment_type = ?, 
                                         film_id_1 = ?, film_meters_1 = ?, film_id_2 = ?, film_meters_2 = ?, 
                                         supply_id_1 = ?, supply_qty_1 = ?, supply_id_2 = ?, supply_qty_2 = ?, 
                                         material_cost = ?, net_profit = ?, comment = ? 
                             WHERE id = ?""",
                  (
                      new_status,
                      final_price,
                      payment_type,
                      f_id_1,
                      m1,
                      f_id_2,
                      m2,
                      s_id_1,
                      q1,
                      s_id_2,
                      q2,
                      mat_cost,
                      net_prof,
                      comment,
                      row["id"],
                  ),
              )
              conn.commit()
              conn.close()
              st.success("Запис успішно оновлено!")
              st.rerun()
    else:
      st.info("Поки немає активних записів.")

  with tab2:
    st.subheader("Створити новий запис")
    services_df = run_query("SELECT * FROM services")

    with st.form("new_appointment_form"):
      st.markdown("### 👤 Дані клієнта та авто")
      c_name = st.text_input("Ім'я та Прізвище клієнта")
      c_phone = st.text_input("Номер телефону")
      car_brand = st.text_input("Марка авто (наприклад, Toyota)")
      car_model = st.text_input("Модель (наприклад, Camry)")
      car_number = st.text_input("Держ. номер")

      st.markdown("### 🛠️ Плановані послуги")
      selected_services = []
      if not services_df.empty:
        selected_services = st.multiselect(
            "Оберіть послуги, які будуть надаватись",
            services_df["service_name"],
        )

      st.markdown("### 📅 Дата та час")
      date = st.date_input("Дата запису")
      time = st.time_input("Час запису")
      comment = st.text_area("Початковий коментар")

      submit_app = st.form_submit_button("Записати клієнта")
      if submit_app:
        if c_name and car_brand:
          conn = sqlite3.connect(DB_NAME)
          cursor = conn.cursor()
          cursor.execute("PRAGMA foreign_keys = ON;")

          cursor.execute(
              """INSERT INTO appointments (client_name, client_phone, car_brand, car_model, car_number, 
                                           date, time, status, final_price, material_cost, net_profit, comment) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, 'Заплановано', 0, 0, 0, ?)""",
              (
                  c_name,
                  c_phone,
                  car_brand,
                  car_model,
                  car_number,
                  str(date),
                  str(time),
                  comment,
              ),
          )
          app_id = cursor.lastrowid

          if selected_services:
            for s_name_item in selected_services:
              s_row = services_df[services_df["service_name"] == s_name_item]
              if not s_row.empty:
                s_id_val = s_row.iloc[0]["id"]
                cursor.execute(
                    "INSERT INTO appointment_services (appointment_id, service_id)"
                    " VALUES (?, ?)",
                    (app_id, s_id_val),
                )

          conn.commit()
          conn.close()
          st.success(f"✅ Записано! Дата запису: {date} о {time}")
        else:
          st.error("Введіть ім'я клієнта та марку автомобіля.")

# 2. СКЛАД
elif menu == "📦 Склад":
  st.header("📦 Облік складу (Плівки та Розхідники)")
  tab1, tab2 = st.tabs(["Залишки на складі", "Додати на склад"])

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
              "Од. виміру (м, шт, л)",
              value=row["unit"],
              key=f"inv_u_{row['id']}",
          )

          col1, col2 = st.columns(2)
          with col1:
            if st.button("Зберегти зміни", key=f"upd_inv_{row['id']}"):
              cost_uah = i_p_usd * i_rate
              run_query(
                  "UPDATE inventory SET item_name = ?, category = ?, width_cm ="
                  " ?, meters_left = ?, price_usd = ?, exchange_rate = ?,"
                  " cost_per_unit_uah = ?, unit = ? WHERE id = ?",
                  (
                      i_name,
                      i_cat,
                      i_width,
                      i_meters,
                      i_p_usd,
                      i_rate,
                      cost_uah,
                      i_unit,
                      row["id"],
                  ),
                  fetch=False,
              )
              st.success("Оновлено!")
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
              st.warning("Видалено!")
              st.rerun()
    else:
      st.info("Склад порожній.")

  with tab2:
    with st.form("add_inventory_form"):
      item_name = st.text_input("Назва (наприклад, LLumar ATR 15)")
      category = st.selectbox("Категорія", ["Плівка", "Розхідник/Хімія"])
      width_cm = st.number_input(
          "Ширина рулону (см, якщо плівка)", value=152.0
      )
      meters_left = st.number_input(
          "Кількість (погонних метрів або штук)", value=30.0
      )
      price_usd = st.number_input("Ціна за одиницю в доларах ($)", value=15.0)
      exchange_rate = st.number_input("Курс долара до гривні", value=41.0)
      unit = st.text_input("Одиниця виміру (м або шт)", value="м")

      if st.form_submit_button("Додати на склад"):
        if item_name:
          cost_uah = price_usd * exchange_rate
          run_query(
              """INSERT INTO inventory (item_name, category, width_cm, meters_left, 
                                           price_usd, exchange_rate, cost_per_unit_uah, unit) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
              (
                  item_name,
                  category,
                  width_cm,
                  meters_left,
                  price_usd,
                  exchange_rate,
                  cost_uah,
                  unit,
              ),
              fetch=False,
          )
          st.success("Додано!")
          st.rerun()

# 3. ПОСЛУГИ
elif menu == "🛠️ Послуги":
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
              st.success("Оновлено!")
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
    with st.form("add_service_form"):
      s_name = st.text_input("Назва послуги (наприклад, Тонування задньої півсфери)")
      s_price = st.number_input("Ціна за замовчуванням (грн)", value=2500.0)
      if st.form_submit_button("Додати послугу"):
        if s_name:
          run_query(
              "INSERT INTO services (service_name, default_price) VALUES (?, ?)",
              (s_name, s_price),
              fetch=False,
          )
          st.success("Додано!")
          st.rerun()

# 4. БАЗА КЛІЄНТІВ ТА БОРГИ
elif menu == "👥 База клієнтів та Борги":
  st.header("👥 База клієнтів, пошук та борги")

  # Боржники (підсвічуємо червоним)
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
          f" (від {d_row['date']})"
      )
    st.markdown("---")

  st.subheader("🔍 Пошук клієнта та історія авто")
  search_query = st.text_input(
      "Введіть ім'я, телефон або марку/номер авто для пошуку"
  )

  if search_query:
    q = f"%{search_query}%"
    client_search_df = run_query(
        """SELECT * FROM appointments 
                                 WHERE client_name LIKE ? OR client_phone LIKE ? OR car_brand LIKE ? OR car_number LIKE ? 
                                 ORDER BY date DESC""",
        (q, q, q, q),
    )
  else:
    client_search_df = run_query(
        "SELECT * FROM appointments ORDER BY date DESC"
    )

  if not client_search_df.empty:
    # Зручний вибір клієнта для перегляду його загальної статистики
    unique_clients = client_search_df["client_name"].unique()
    selected_client = st.selectbox(
        "Виберіть клієнта з результатів для детального перегляду",
        ["Всі клієнти"] + list(unique_clients),
    )

    if selected_client != "Всі клієнти":
      filtered_client_df = client_search_df[
          client_search_df["client_name"] == selected_client
      ]
      total_spent = filtered_client_df[filtered_client_df["status"] == "Виконано"][
          "final_price"
      ].sum()
      st.info(
          f"👤 **Клієнт:** {selected_client} | 📞 **Телефон:**"
          f" {filtered_client_df.iloc[0]['client_phone']} | 💰 **Загалом"
          f" сплачено за весь період:** {total_spent:,.2f} грн"
      )

      display_df = filtered_client_df[[
          "date",
          "car_brand",
          "car_model",
          "car_number",
          "status",
          "payment_type",
          "final_price",
          "comment",
      ]]
      display_df.columns = [
          "Дата",
          "Марка",
          "Модель",
          "Держ. номер",
          "Статус",
          "Оплата",
          "Ціна (грн)",
          "Коментар",
      ]
      st.dataframe(display_df, use_container_width=True)
    else:
      display_df = client_search_df[[
          "date",
          "client_name",
          "client_phone",
          "car_brand",
          "car_model",
          "car_number",
          "status",
          "payment_type",
          "final_price",
      ]]
      display_df.columns = [
          "Дата",
          "Клієнт",
          "Телефон",
          "Марка",
          "Модель",
          "Держ. номер",
          "Статус",
          "Оплата",
          "Ціна (грн)",
      ]
      st.dataframe(display_df, use_container_width=True)
  else:
    st.info("Нічого не знайдено.")

# 5. ЗВІТИ ТА АНАЛІТИКА
elif menu == "📊 Звіти та Аналітика":
  st.header("📊 Фінансова аналітика та звіти")

  # Отримуємо всі виконані роботи
  rep_df = run_query(
      "SELECT * FROM appointments WHERE status = 'Виконано' ORDER BY date DESC"
  )

  if not rep_df.empty:
    # Додаємо вибір періоду (Місяць / Рік / За весь час)
    rep_df["date_dt"] = pd.to_datetime(rep_df["date"])
    rep_df["Рік-Місяць"] = rep_df["date_dt"].dt.strftime("%Y-%m")

    period_options = ["За весь час"] + sorted(
        rep_df["Рік-Місяць"].unique().tolist(), reverse=True
    )
    selected_period = st.selectbox("Виберіть період для аналітики", period_options)

    if selected_period != "За весь час":
      filtered_rep = rep_df[rep_df["Рік-Місяць"] == selected_period]
      st.subheader(
          f"📊 Звіт за період: {selected_period} (з 1 числа по кінець місяця)"
      )
    else:
      filtered_rep = rep_df
      st.subheader("📊 Звіт за весь час")

    if not filtered_rep.empty:
      total_earned = filtered_rep["final_price"].sum()
      total_cost = filtered_rep["material_cost"].sum()
      total_net = filtered_rep["net_profit"].sum()
      total_cars = len(filtered_rep)

      col1, col2, col3, col4 = st.columns(4)
      col1.metric("Виконано авто", f"{total_cars} шт")
      col2.metric("Загальний дохід", f"{total_earned:,.2f} грн")
      col3.metric("Витрати на матеріали", f"{total_cost:,.2f} грн")
      col4.metric("Чистий прибуток", f"{total_net:,.2f} грн")

      st.markdown("---")
      st.subheader("Детальна таблиця виконаних робіт")

      formatted_rep = filtered_rep[[
          "date",
          "client_name",
          "car_brand",
          "car_model",
          "car_number",
          "payment_type",
          "final_price",
          "material_cost",
          "net_profit",
          "comment",
      ]].copy()
      formatted_rep.columns = [
          "Дата",
          "Клієнт",
          "Марка",
          "Модель",
          "Держ. номер",
          "Оплата",
          "Дохід (грн)",
          "Собівартість мат.",
          "Прибуток (грн)",
          "Коментар",
      ]
      st.dataframe(formatted_rep, use_container_width=True)
    else:
      st.info("За обраний період немає виконаних робіт.")
  else:
    st.info(
        "Немає даних для звітів (потрібно перевести хоча б один запис у статус"
        " 'Виконано')."
    )
