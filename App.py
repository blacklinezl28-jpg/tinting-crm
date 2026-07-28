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
      " AUTOINCREMENT, item_name TEXT, category TEXT, unit TEXT,"
      " quantity_left REAL, cost_per_unit REAL)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, client_name TEXT, client_phone TEXT, car_brand TEXT,"
      " car_model TEXT, car_number TEXT, date TEXT, time TEXT, status TEXT,"
      " final_price REAL, film_id INTEGER, film_meters REAL, supply_id INTEGER,"
      " supply_qty REAL, material_cost REAL, net_profit REAL, comment TEXT,"
      " photo_before TEXT, photo_after TEXT)"
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


st.sidebar.title("🚗 Меню CRM")
menu = st.sidebar.selectbox(
    "Виберіть розділ", [
        "🛠️ Послуги",
        "📦 Склад (Плівки та Розхідники)",
        "📅 Записи",
        "👥 База клієнтів (Архів)",
        "📊 Аналітика та Звіти",
    ]
)

# 1. ПОСЛУГИ
if menu == "🛠️ Послуги":
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
              "Ціна (грн)",
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
          st.success("Послугу додано!")
          st.rerun()

# 2. СКЛАД
elif menu == "📦 Склад (Плівки та Розхідники)":
  st.header("📦 Склад матеріалів та розхідників")
  tab1, tab2 = st.tabs(["Залишки на складі", "Додати на склад"])

  with tab1:
    inv_df = run_query("SELECT * FROM inventory")
    if not inv_df.empty:
      for idx, row in inv_df.iterrows():
        with st.expander(
            f"{row['item_name']} ({row['category']}) — Залишок:"
            f" {row['quantity_left']} {row['unit']}"
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
          i_qty = st.number_input(
              "Залишок",
              value=float(row["quantity_left"]),
              key=f"inv_q_{row['id']}",
          )
          i_unit = st.text_input(
              "Од. виміру (м, шт, л)",
              value=row["unit"],
              key=f"inv_u_{row['id']}",
          )
          i_cost = st.number_input(
              "Ціна за одиницю (грн)",
              value=float(row["cost_per_unit"]),
              key=f"inv_co_{row['id']}",
          )
          col1, col2 = st.columns(2)
          with col1:
            if st.button("Оновити позицію", key=f"upd_inv_{row['id']}"):
              run_query(
                  "UPDATE inventory SET item_name = ?, category = ?, unit = ?,"
                  " quantity_left = ?, cost_per_unit = ? WHERE id = ?",
                  (i_name, i_cat, i_unit, i_qty, i_cost, row["id"]),
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
      item_name = st.text_input("Назва (наприклад, LLumar ATR 15 або Лезвія)")
      category = st.selectbox("Категорія", ["Плівка", "Розхідник/Хімія"])
      quantity_left = st.number_input("Кількість (метрів або штук)", value=30.0)
      unit = st.text_input("Одиниця виміру", value="м")
      cost_per_unit = st.number_input(
          "Вартість за одиницю (собівартість у грн)", value=350.0
      )
      if st.form_submit_button("Додати на склад"):
        if item_name:
          run_query(
              "INSERT INTO inventory (item_name, category, unit,"
              " quantity_left, cost_per_unit) VALUES (?, ?, ?, ?, ?)",
              (item_name, category, unit, quantity_left, cost_per_unit),
              fetch=False,
          )
          st.success("Успішно додано на склад!")
          st.rerun()

# 3. ЗАПИСИ
elif menu == "📅 Записи":
  st.header("📅 Журнал записів")
  tab1, tab2 = st.tabs(["Список записів", "➕ Створити новий запис"])

  with tab1:
    apps = run_query("SELECT * FROM appointments ORDER BY date DESC")
    if not apps.empty:
      for idx, row in apps.iterrows():
        status_color = (
            "🟢"
            if row["status"] == "Виконано"
            else "🟡" if row["status"] == "В роботі" else "🔵"
        )
        with st.expander(
            f"{status_color} {row['date']} {row['time']} | {row['client_name']}"
            f" ({row['car_brand']} {row['car_model']} - {row['car_number']}) |"
            f" Статус: {row['status']}"
        ):
          st.write(f"**Телефон:** {row['client_phone']}")
          st.write(f"**Статус:** {row['status']}")

          # Отримуємо послуги для цього запису
          srv_ids = run_query(
              "SELECT service_id FROM appointment_services WHERE appointment_id"
              " = ?",
              (row["id"],),
          )
          if not srv_ids.empty:
            all_s = run_query("SELECT * FROM services")
            matched_services = all_s[all_s["id"].isin(srv_ids["service_id"])]
            st.write(
                "**Заплановані послуги:**"
                f" {', '.join(matched_services['service_name'].tolist())}"
            )

          st.markdown("---")
          # Форма оновлення статусу та фінішної обробки
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

            inv_data = run_query("SELECT * FROM inventory")
            films = inv_data[inv_data["category"] == "Плівка"]
            supplies = inv_data[inv_data["category"] != "Плівка"]

            film_options = {"Не вибрано": None}
            for _, f_row in films.iterrows():
              film_options[
                  f"{f_row['item_name']} (залишок: {f_row['quantity_left']}"
                  f" {f_row['unit']})"
              ] = f_row["id"]

            sel_film_label = st.selectbox(
                "Використана плівка", list(film_options.keys())
            )
            film_meters = st.number_input(
                "Використано метрів плівки",
                value=(
                    float(row["film_meters"])
                    if pd.notna(row["film_meters"])
                    else 0.0
                ),
            )

            supp_options = {"Не вибрано": None}
            for _, s_row in supplies.iterrows():
              supp_options[
                  f"{s_row['item_name']} (залишок: {s_row['quantity_left']}"
                  f" {s_row['unit']})"
              ] = s_row["id"]

            sel_supp_label = st.selectbox(
                "Використаний розхідник", list(supp_options.keys())
            )
            supp_qty = st.number_input(
                "Кількість розхідника",
                value=(
                    float(row["supply_qty"])
                    if pd.notna(row["supply_qty"])
                    else 0.0
                ),
            )

            comment = st.text_area(
                "Коментар / Нотатки",
                value=str(row["comment"]) if pd.notna(row["comment"]) else "",
            )

            submitted = st.form_submit_button("Зберегти / Оновити запис")
            if submitted:
              f_id = film_options[sel_film_label]
              s_id = supp_options[sel_supp_label]

              # Розрахунок собівабітості матеріалів
              mat_cost = 0.0
              conn = sqlite3.connect(DB_NAME)
              cursor = conn.cursor()

              if f_id and film_meters > 0:
                cursor.execute(
                    "SELECT cost_per_unit, quantity_left FROM inventory WHERE"
                    " id = ?",
                    (f_id,),
                )
                f_res = cursor.fetchone()
                if f_res:
                  mat_cost += f_res[0] * film_meters
                  # Якщо статус змінюється на Виконано і раніше не списувалося (тут робимо спрощене списання)
                  if new_status == "Виконано" and row["status"] != "Виконано":
                    cursor.execute(
                        "UPDATE inventory SET quantity_left = quantity_left - ?"
                        " WHERE id = ?",
                        (film_meters, f_id),
                    )

              if s_id and supp_qty > 0:
                cursor.execute(
                    "SELECT cost_per_unit, quantity_left FROM inventory WHERE"
                    " id = ?",
                    (s_id,),
                )
                s_res = cursor.fetchone()
                if s_res:
                  mat_cost += s_res[0] * supp_qty
                  if new_status == "Виконано" and row["status"] != "Виконано":
                    cursor.execute(
                        "UPDATE inventory SET quantity_left = quantity_left - ?"
                        " WHERE id = ?",
                        (supp_qty, s_id),
                    )

              net_prof = final_price - mat_cost

              cursor.execute(
                  """UPDATE appointments SET status = ?, final_price = ?, film_id = ?, film_meters = ?, 
                                         supply_id = ?, supply_qty = ?, material_cost = ?, net_profit = ?, comment = ? 
                             WHERE id = ?""",
                  (
                      new_status,
                      final_price,
                      f_id,
                      film_meters,
                      s_id,
                      supp_qty,
                      mat_cost,
                      net_prof,
                      comment,
                      row["id"],
                  ),
              )
              conn.commit()
              conn.close()
              st.success("Запис успішно оновлено та склад скориговано!")
              st.rerun()
    else:
      st.info("Поки немає жодного запису.")

  with tab2:
    st.subheader("Створити новий запис")
    services_df = run_query("SELECT * FROM services")

    with st.form("new_appointment_form"):
      st.markdown("### 👤 Дані клієнта та авто")
      c_name = st.text_input("Ім'я та Прізвище клієнта")
      c_phone = st.text_input("Номер телефону")
      car_brand = st.text_input("Марка авто (наприклад, BMW)")
      car_model = st.text_input("Модель (наприклад, X5)")
      car_number = st.text_input("Держ. номер")

      st.markdown("### 🛠️ Плановані послуги")
      selected_services = []
      if not services_df.empty:
        selected_services = st.multiselect(
            "Оберіть послуги, які будуть надаватись",
            services_df["service_name"],
        )

      st.markdown("### 📅 Дата та статус")
      date = st.date_input("Дата запису")
      time = st.time_input("Час запису")
      status = st.selectbox(
          "Статус", ["Заплановано", "В роботі", "Виконано", "Скасовано"]
      )
      comment = st.text_area("Початковий коментар")

      submit_app = st.form_submit_button("Створити запис")
      if submit_app:
        if c_name and car_brand:
          conn = sqlite3.connect(DB_NAME)
          cursor = conn.cursor()
          cursor.execute("PRAGMA foreign_keys = ON;")

          cursor.execute(
              """INSERT INTO appointments (client_name, client_phone, car_brand, car_model, car_number, 
                                           date, time, status, final_price, material_cost, net_profit, comment) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?)""",
              (
                  c_name,
                  c_phone,
                  car_brand,
                  car_model,
                  car_number,
                  str(date),
                  str(time),
                  status,
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
          st.success("Запис успішно створено!")
          st.rerun()
        else:
          st.error("Введіть ім'я клієнта та марку автомобіля.")

# 4. БАЗА КЛІЄНТІВ (АРХІВ)
elif menu == "👥 База клієнтів (Архів)":
  st.header("👥 База клієнтів та історія авто")
  archive_df = run_query(
      "SELECT client_name, client_phone, car_brand, car_model, car_number,"
      " date, status, final_price FROM appointments ORDER BY date DESC"
  )
  if not archive_df.empty:
    st.dataframe(archive_df, use_container_width=True)
  else:
    st.info("Архів порожній.")

# 5. АНАЛІТИКА ТА ЗВІТИ
elif menu == "📊 Аналітика та Звіти":
  st.header("📊 Фінансова аналітика та звіти")
  rep_df = run_query(
      "SELECT * FROM appointments WHERE status = 'Виконано'"
  )

  if not rep_df.empty:
    total_earned = rep_df["final_price"].sum()
    total_cost = rep_df["material_cost"].sum()
    total_net = rep_df["net_profit"].sum()
    total_cars = len(rep_df)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Виконано авто", f"{total_cars} шт")
    col2.metric("Загальний дохід", f"{total_earned:,.2f} грн")
    col3.metric("Витрати на матеріали", f"{total_cost:,.2f} грн")
    col4.metric("Чистий прибуток", f"{total_net:,.2f} грн")

    st.markdown("---")
    st.subheader("Детальний звіт по всіх виконаних роботах")
    st.dataframe(
        rep_df[[
            "date",
            "client_name",
            "car_brand",
            "car_model",
            "car_number",
            "final_price",
            "material_cost",
            "net_profit",
            "comment",
        ]],
        use_container_width=True,
    )
  else:
    st.info(
        "Немає даних для звітів (потрібно перевести хоча б один запис у статус"
        " 'Виконано')."
    )
