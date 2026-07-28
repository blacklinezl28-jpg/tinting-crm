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
  # Увімкнення підтримки зовнішніх ключів (Foreign Keys) для каскадного видалення
  cursor.execute("PRAGMA foreign_keys = ON;")

  cursor.execute(
      "CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, name TEXT, phone TEXT)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS cars (id INTEGER PRIMARY KEY AUTOINCREMENT,"
      " client_id INTEGER, car_brand TEXT, car_model TEXT, car_number TEXT,"
      " car_year INTEGER, FOREIGN KEY(client_id) REFERENCES clients(id) ON"
      " DELETE CASCADE)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS services (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, service_name TEXT, default_price REAL)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, film_name TEXT, category TEXT, width_cm REAL,"
      " meters_left REAL, min_limit REAL, price_usd REAL, exchange_rate REAL,"
      " cost_per_meter_uah REAL)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS supplies (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, item_name TEXT, quantity REAL, unit TEXT, cost REAL)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY"
      " AUTOINCREMENT, client_id INTEGER, car_id INTEGER, film_id INTEGER,"
      " meters_used REAL, supply_id INTEGER, supply_qty REAL, total_price REAL,"
      " payment_type TEXT, cost_price REAL, master_percent REAL,"
      " master_payout REAL, status TEXT, date TEXT, time TEXT, warranty_months"
      " INTEGER, comment TEXT, FOREIGN KEY(client_id) REFERENCES clients(id)"
      " ON DELETE CASCADE, FOREIGN KEY(car_id) REFERENCES cars(id) ON DELETE"
      " CASCADE, FOREIGN KEY(film_id) REFERENCES inventory(id) ON DELETE SET"
      " NULL, FOREIGN KEY(supply_id) REFERENCES supplies(id) ON DELETE SET"
      " NULL)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS appointment_services (appointment_id"
      " INTEGER, service_id INTEGER, FOREIGN KEY(appointment_id) REFERENCES"
      " appointments(id) ON DELETE CASCADE, FOREIGN KEY(service_id) REFERENCES"
      " services(id) ON DELETE CASCADE)"
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


def get_clients():
  return run_query("SELECT * FROM clients")


def get_cars():
  return run_query(
      "SELECT cars.id, clients.name as client_name, cars.car_brand,"
      " cars.car_model, cars.car_number, cars.car_year, cars.client_id FROM"
      " cars JOIN clients ON cars.client_id = clients.id"
  )


def get_inventory():
  return run_query("SELECT * FROM inventory")


def get_supplies():
  return run_query("SELECT * FROM supplies")


def get_services():
  return run_query("SELECT * FROM services")


st.sidebar.title("🚗 Меню CRM")
menu = st.sidebar.selectbox(
    "Виберіть розділ", [
        "👥 Клієнти та Авто",
        "🎞️ Склад плівок",
        "📦 Розхідники",
        "🛠️ Послуги",
        "📅 Записи",
        "📊 Звіти",
    ]
)

if menu == "👥 Клієнти та Авто":
  st.header("👥 Клієнти та автомобілі")
  tab1, tab2, tab3 = st.tabs(
      ["Список та Редагування", "Додати клієнта", "Додати авто"]
  )

  with tab1:
    st.subheader("Керування клієнтами та авто")
    clients_df = get_clients()
    if not clients_df.empty:
      selected_client_name = st.selectbox(
          "Виберіть клієнта для редагування/видалення", clients_df["name"]
      )
      client_row = clients_df[
          clients_df["name"] == selected_client_name
      ].iloc[0]
      c_id = client_row["id"]

      new_c_name = st.text_input(
          "Ім'я клієнта", value=client_row["name"], key="edit_c_name"
      )
      new_c_phone = st.text_input(
          "Телефон", value=str(client_row["phone"]), key="edit_c_phone"
      )

      col1, col2 = st.columns(2)
      with col1:
        if st.button("Зберегти зміни клієнта"):
          run_query(
              "UPDATE clients SET name = ?, phone = ? WHERE id = ?",
              (new_c_name, new_c_phone, c_id),
              fetch=False,
          )
          st.success("Дані клієнта оновлено!")
          st.rerun()
      with col2:
        if st.button(
            "Видалити клієнта (та всі його авто)", type="primary"
        ):
          run_query(
              "DELETE FROM clients WHERE id = ?", (c_id,), fetch=False
          )
          st.warning("Клієнта та його автомобілі видалено!")
          st.rerun()

      st.markdown("---")
      st.subheader("Автомобілі цього клієнта")
      cars_df = run_query(
          "SELECT * FROM cars WHERE client_id = ?", (c_id,)
      )
      if not cars_df.empty:
        for index, car in cars_df.iterrows():
          with st.expander(
              f"{car['car_brand']} {car['car_model']} ({car['car_number']})"
          ):
            e_brand = st.text_input(
                "Марка", value=car["car_brand"], key=f"car_b_{car['id']}"
            )
            e_model = st.text_input(
                "Модель", value=car["car_model"], key=f"car_m_{car['id']}"
            )
            e_num = st.text_input(
                "Номер", value=car["car_number"], key=f"car_n_{car['id']}"
            )
            e_year = st.number_input(
                "Рік",
                value=int(car["car_year"]) if car["car_year"] else 2020,
                key=f"car_y_{car['id']}",
            )

            col_a, col_b = st.columns(2)
            with col_a:
              if st.button("Оновити авто", key=f"upd_car_{car['id']}"):
                run_query(
                    "UPDATE cars SET car_brand = ?, car_model = ?, car_number ="
                    " ?, car_year = ? WHERE id = ?",
                    (e_brand, e_model, e_num, e_year, car["id"]),
                    fetch=False,
                )
                st.success("Авто оновлено!")
                st.rerun()
            with col_b:
              if st.button(
                  "Видалити авто",
                  key=f"del_car_{car['id']}",
                  type="secondary",
              ):
                run_query(
                    "DELETE FROM cars WHERE id = ?", (car["id"],), fetch=False
                )
                st.warning("Авто видалено!")
                st.rerun()
      else:
        st.info("У цього клієнта поки немає доданих автомобілів.")
    else:
      st.info("Список клієнтів порожній.")

  with tab2:
    st.subheader("Новий клієнт")
    with st.form("client_form"):
      name = st.text_input("Ім'я та Прізвище")
      phone = st.text_input("Телефон")
      submitted = st.form_submit_button("Додати клієнта")
      if submitted and name:
        run_query(
            "INSERT INTO clients (name, phone) VALUES (?, ?)",
            (name, phone),
            fetch=False,
        )
        st.success(f"Клієнта {name} додано!")
        st.rerun()

  with tab3:
    st.subheader("Новий автомобіль")
    clients_df = get_clients()
    if not clients_df.empty:
      client_dict = dict(zip(clients_df["name"], clients_df["id"]))
      with st.form("car_form"):
        selected_client = st.selectbox(
            "Виберіть клієнта", list(client_dict.keys())
        )
        brand = st.text_input("Марка авто (наприклад, BMW)")
        model = st.text_input("Модель (наприклад, X5)")
        number = st.text_input("Держ. номер")
        year = st.number_input(
            "Рік випуску", min_value=1990, max_value=2030, value=2021
        )
        car_submitted = st.form_submit_button("Додати автомобіль")
        if car_submitted and brand:
          client_id = client_dict[selected_client]
          run_query(
              "INSERT INTO cars (client_id, car_brand, car_model, car_number,"
              " car_year) VALUES (?, ?, ?, ?, ?)",
              (client_id, brand, model, number, year),
              fetch=False,
          )
          st.success("Автомобіль успішно додано!")
          st.rerun()
    else:
      st.warning("Спочатку додайте хоча б одного клієнта.")
elif menu == "🎞️ Склад плівок":
  st.header("🎞️ Облік плівок на складі")
  tab1, tab2 = st.tabs(["Список плівок та Редагування", "Додати плівку"])

  with tab1:
    inv_df = get_inventory()
    if not inv_df.empty:
      selected_film = st.selectbox(
          "Виберіть плівку для редагування/видалення", inv_df["film_name"]
      )
      film_row = inv_df[inv_df["film_name"] == selected_film].iloc[0]
      f_id = film_row["id"]

      f_name = st.text_input(
          "Назва плівки", value=film_row["film_name"], key="edit_f_name"
      )
      f_cat = st.text_input(
          "Категорія", value=film_row["category"], key="edit_f_cat"
      )
      f_width = st.number_input(
          "Ширина (см)",
          value=float(film_row["width_cm"]),
          key="edit_f_width",
      )
      f_meters = st.number_input(
          "Залишок метрів",
          value=float(film_row["meters_left"]),
          key="edit_f_meters",
      )
      f_min = st.number_input(
          "Мінімальний ліміт",
          value=float(film_row["min_limit"]),
          key="edit_f_min",
      )
      f_price = st.number_input(
          "Ціна ($)", value=float(film_row["price_usd"]), key="edit_f_price"
      )
      f_rate = st.number_input(
          "Курс валюти",
          value=float(film_row["exchange_rate"]),
          key="edit_f_rate",
      )

      col1, col2 = st.columns(2)
      with col1:
        if st.button("Зберегти плівку"):
          cost_uah = f_price * f_rate
          run_query(
              "UPDATE inventory SET film_name = ?, category = ?, width_cm = ?,"
              " meters_left = ?, min_limit = ?, price_usd = ?, exchange_rate ="
              " ?, cost_per_meter_uah = ? WHERE id = ?",
              (
                  f_name,
                  f_cat,
                  f_width,
                  f_meters,
                  f_min,
                  f_price,
                  f_rate,
                  cost_uah,
                  f_id,
              ),
              fetch=False,
          )
          st.success("Плівку оновлено!")
          st.rerun()
      with col2:
        if st.button("Видалити плівку", type="primary"):
          run_query("DELETE FROM inventory WHERE id = ?", (f_id,), fetch=False)
          st.warning("Плівку видалено!")
          st.rerun()

      st.markdown("---")
      st.dataframe(inv_df, use_container_width=True)
    else:
      st.info("Склад плівок порожній.")

  with tab2:
    with st.form("film_form"):
      film_name = st.text_input("Назва плівки (наприклад, LLumar ATR 15)")
      category = st.selectbox(
          "Категорія", ["Тонувальна", "Атермальна", "Бронеплівка", "Вініл"]
      )
      width_cm = st.number_input("Ширина рулону (см)", value=152.0)
      meters_left = st.number_input("Кількість метрів", value=30.0)
      min_limit = st.number_input("Мін. ліміт для попередження", value=5.0)
      price_usd = st.number_input("Ціна за метр ($)", value=15.0)
      exchange_rate = st.number_input("Курс валюти (грн)", value=41.0)
      submitted = st.form_submit_button("Додати плівку")
      if submitted and film_name:
        cost_uah = price_usd * exchange_rate
        run_query(
            "INSERT INTO inventory (film_name, category, width_cm, meters_left,"
            " min_limit, price_usd, exchange_rate, cost_per_meter_uah) VALUES"
            " (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                film_name,
                category,
                width_cm,
                meters_left,
                min_limit,
                price_usd,
                exchange_rate,
                cost_uah,
            ),
            fetch=False,
        )
        st.success("Плівку успішно додано!")
        st.rerun()

elif menu == "📦 Розхідники":
  st.header("📦 Облік розхідників та хімії")
  tab1, tab2 = st.tabs(["Список та Редагування", "Додати розхідник"])

  with tab1:
    supp_df = get_supplies()
    if not supp_df.empty:
      selected_supp = st.selectbox(
          "Виберіть розхідник для редагування/видалення", supp_df["item_name"]
      )
      supp_row = supp_df[supp_df["item_name"] == selected_supp].iloc[0]
      s_id = supp_row["id"]

      s_name = st.text_input(
          "Назва", value=supp_row["item_name"], key="edit_s_name"
      )
      s_qty = st.number_input(
          "Кількість",
          value=float(supp_row["quantity"]),
          key="edit_s_qty",
      )
      s_unit = st.text_input(
          "Одиниця виміру", value=supp_row["unit"], key="edit_s_unit"
      )
      s_cost = st.number_input(
          "Вартість (грн)",
          value=float(supp_row["cost"]),
          key="edit_s_cost",
      )

      col1, col2 = st.columns(2)
      with col1:
        if st.button("Зберегти розхідник"):
          run_query(
              "UPDATE supplies SET item_name = ?, quantity = ?, unit = ?, cost"
              " = ? WHERE id = ?",
              (s_name, s_qty, s_unit, s_cost, s_id),
              fetch=False,
          )
          st.success("Розхідник оновлено!")
          st.rerun()
      with col2:
        if st.button("Видалити розхідник", type="primary"):
          run_query("DELETE FROM supplies WHERE id = ?", (s_id,), fetch=False)
          st.warning("Розхідник видалено!")
          st.rerun()

      st.markdown("---")
      st.dataframe(supp_df, use_container_width=True)
    else:
      st.info("Список розхідників порожній.")

  with tab2:
    with st.form("supp_form"):
      item_name = st.text_input("Назва (наприклад, Лезвія Olfa, Шампунь)")
      quantity = st.number_input("Кількість", value=10.0)
      unit = st.text_input("Одиниця виміру (шт, л, рулон)", value="шт")
      cost = st.number_input("Загальна вартість (грн)", value=200.0)
      submitted = st.form_submit_button("Додати розхідник")
      if submitted and item_name:
        run_query(
            "INSERT INTO supplies (item_name, quantity, unit, cost) VALUES"
            " (?, ?, ?, ?)",
            (item_name, quantity, unit, cost),
            fetch=False,
        )
        st.success("Розхідник додано!")
        st.rerun()

elif menu == "🛠️ Послуги":
  st.header("🛠️ Додаткові послуги")
  tab1, tab2 = st.tabs(["Список послуг та Редагування", "Додати послугу"])

  with tab1:
    serv_df = get_services()
    if not serv_df.empty:
      selected_serv = st.selectbox(
          "Виберіть послугу для редагування/видалення", serv_df["service_name"]
      )
      serv_row = serv_df[serv_df["service_name"] == selected_serv].iloc[0]
      srv_id = serv_row["id"]

      srv_name = st.text_input(
          "Назва послуги",
          value=serv_row["service_name"],
          key="edit_srv_name",
      )
      srv_price = st.number_input(
          "Ціна за замовчуванням (грн)",
          value=float(serv_row["default_price"]),
          key="edit_srv_price",
      )

      col1, col2 = st.columns(2)
      with col1:
        if st.button("Зберегти послугу"):
          run_query(
              "UPDATE services SET service_name = ?, default_price = ? WHERE"
              " id = ?",
              (srv_name, srv_price, srv_id),
              fetch=False,
          )
          st.success("Послугу оновлено!")
          st.rerun()
      with col2:
        if st.button("Видалити послугу", type="primary"):
          run_query("DELETE FROM services WHERE id = ?", (srv_id,), fetch=False)
          st.warning("Послугу видалено!")
          st.rerun()

      st.markdown("---")
      st.dataframe(serv_df, use_container_width=True)
    else:
      st.info("Список послуг порожній.")

  with tab2:
    with st.form("service_form"):
      service_name = st.text_input(
          "Назва послуги (наприклад, Демонтаж старого тонування)"
      )
      default_price = st.number_input("Ціна (грн)", value=500.0)
      submitted = st.form_submit_button("Додати послугу")
      if submitted and service_name:
        run_query(
            "INSERT INTO services (service_name, default_price) VALUES (?, ?)",
            (service_name, default_price),
            fetch=False,
        )
        st.success("Послугу додано!")
        st.rerun()
      elif menu == "📅 Записи":
  st.header("📅 Журнал записів")
  tab1, tab2, tab3 = st.tabs(["Всі записи", "Новий запис", "Керування записом"])

  with tab1:
    st.subheader("Список усіх записів")
    appointments_df = run_query("""
            SELECT appointments.id, clients.name as client, cars.car_brand || ' ' || cars.car_model as car, 
                   appointments.total_price, appointments.status, appointments.date, appointments.time 
            FROM appointments 
            JOIN clients ON appointments.client_id = clients.id 
            JOIN cars ON appointments.car_id = cars.id
        """)
    if not appointments_df.empty:
      st.dataframe(appointments_df, use_container_width=True)
    else:
      st.info("Поки немає жодного запису.")

  with tab2:
    st.subheader("Створити новий запис")
    clients_df = get_clients()
    cars_df = get_cars()
    inv_df = get_inventory()
    supp_df = get_supplies()
    serv_df = get_services()

    if clients_df.empty or cars_df.empty:
      st.warning(
          "Спочатку додайте хоча б одного клієнта та автомобіль у розділі"
          " 'Клієнти та Авто'."
      )
    else:
      with st.form("appointment_form"):
        client_dict = dict(zip(clients_df["name"], clients_df["id"]))
        sel_client_name = st.selectbox("Клієнт", list(client_dict.keys()))
        client_id = client_dict[sel_client_name]

        client_cars = cars_df[cars_df["client_id"] == client_id]
        if not client_cars.empty:
          car_dict = dict(
              zip(
                  client_cars["car_brand"]
                  + " "
                  + client_cars["car_model"]
                  + " ("
                  + client_cars["car_number"]
                  + ")",
                  client_cars["id"],
              )
          )
          sel_car_name = st.selectbox(
              "Автомобіль клієнта", list(car_dict.keys())
          )
          car_id = car_dict[sel_car_name]
        else:
          st.error("У цього клієнта немає автомобілів!")
          car_id = None

        film_id, meters_used = None, 0.0
        if not inv_df.empty:
          film_dict = dict(zip(inv_df["film_name"], inv_df["id"]))
          sel_film = st.selectbox(
              "Плівка (якщо використовується)",
              ["Не вибрано"] + list(film_dict.keys()),
          )
          if sel_film != "Не вибрано":
            film_id = film_dict[sel_film]
            meters_used = st.number_input("Використано метрів", value=2.0)

        selected_services = []
        if not serv_df.empty:
          selected_services = st.multiselect(
              "Додаткові послуги", serv_df["service_name"]
          )

        supply_id, supply_qty = None, 0.0
        if not supp_df.empty:
          supp_dict = dict(zip(supp_df["item_name"], supp_df["id"]))
          sel_supp = st.selectbox(
              "Витратний матеріал", ["Не вибрано"] + list(supp_dict.keys())
          )
          if sel_supp != "Не вибрано":
            supply_id = supp_dict[sel_supp]
            supply_qty = st.number_input("Кількість витратника", value=1.0)

        total_price = st.number_input(
            "Загальна сума до сплати (грн)", value=3000.0
        )
        payment_type = st.selectbox(
            "Тип оплати", ["Готівка", "Картка", "Безготівковий"]
        )
        master_percent = st.slider("Відсоток майстра (%)", 0, 100, 40)
        master_payout = total_price * (master_percent / 100.0)

        status = st.selectbox(
            "Статус", ["Заплановано", "В роботі", "Виконано", "Скасовано"]
        )
        date = st.date_input("Дата")
        time = st.time_input("Час")
        warranty_months = st.number_input("Гарантія (місяців)", value=12)
        comment = st.text_area("Коментар / Нотатки")

        app_submitted = st.form_submit_button("Зберегти запис")
        if app_submitted and car_id:
          conn = sqlite3.connect(DB_NAME)
          cursor = conn.cursor()
          cursor.execute("PRAGMA foreign_keys = ON;")
          cursor.execute(
              """INSERT INTO appointments (client_id, car_id, film_id, meters_used, supply_id, 
                                           supply_qty, total_price, payment_type, cost_price, 
                                           master_percent, master_payout, status, date, time, 
                                           warranty_months, comment) 
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (
                  client_id,
                  car_id,
                  film_id,
                  meters_used,
                  supply_id,
                  supply_qty,
                  total_price,
                  payment_type,
                  0,
                  master_percent,
                  master_payout,
                  status,
                  str(date),
                  str(time),
                  warranty_months,
                  comment,
              ),
          )
          app_id = cursor.lastrowid

          # Автоматичне списування плівки зі складу при створенні запису
          if film_id and meters_used > 0:
            cursor.execute(
                "UPDATE inventory SET meters_left = meters_left - ? WHERE id = ?",
                (meters_used, film_id),
            )

          if selected_services:
            for s_name_item in selected_services:
              s_row = serv_df[serv_df["service_name"] == s_name_item]
              if not s_row.empty:
                s_id_val = s_row.iloc[0]["id"]
                cursor.execute(
                    "INSERT INTO appointment_services (appointment_id, service_id)"
                    " VALUES (?, ?)",
                    (app_id, s_id_val),
                )

          conn.commit()
          conn.close()
          st.success("Запис успішно створено, а склад оновлено!")
          st.rerun()

  with tab3:
    st.subheader("Редагування або видалення запису")
    app_list_df = run_query("""
            SELECT appointments.id, clients.name || ' - ' || cars.car_brand || ' (' || appointments.date || ')' as info 
            FROM appointments 
            JOIN clients ON appointments.client_id = clients.id 
            JOIN cars ON appointments.car_id = cars.id
        """)
    if not app_list_df.empty:
      selected_app_info = st.selectbox("Виберіть запис", app_list_df["info"])
      app_id_to_edit = app_list_df[
          app_list_df["info"] == selected_app_info
      ].iloc[0]["id"]

      cur_app_df = run_query(
          "SELECT * FROM appointments WHERE id = ?", (app_id_to_edit,)
      )
      if not cur_app_df.empty:
        curr_row = cur_app_df.iloc[0]
        statuses = ["Заплановано", "В роботі", "Виконано", "Скасовано"]
        curr_status = (
            curr_row["status"] if curr_row["status"] in statuses else "Заплановано"
        )
        new_status = st.selectbox(
            "Змінити статус", statuses, index=statuses.index(curr_status)
        )
        new_price = st.number_input(
            "Сума (грн)", value=float(curr_row["total_price"])
        )

        col1, col2 = st.columns(2)
        with col1:
          if st.button("Оновити статус/суму"):
            run_query(
                "UPDATE appointments SET status = ?, total_price = ? WHERE id"
                " = ?",
                (new_status, new_price, app_id_to_edit),
                fetch=False,
            )
            st.success("Запис оновлено!")
            st.rerun()
        with col2:
          if st.button("Видалити запис", type="primary"):
            run_query(
                "DELETE FROM appointments WHERE id = ?",
                (app_id_to_edit,),
                fetch=False,
            )
            st.warning("Запис видалено!")
            st.rerun()
    else:
      st.info("Немає записів для редагування.")

elif menu == "📊 Звіти":
  st.header("📊 Аналітика та фінансові звіти")
  app_rep = run_query(
      "SELECT total_price, master_payout, date, status FROM appointments"
  )
  if not app_rep.empty:
    total_earned = app_rep[app_rep["status"] == "Виконано"][
        "total_price"
    ].sum()
    total_master = app_rep[app_rep["status"] == "Виконано"][
        "master_payout"
    ].sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Загальний дохід (Виконано)", f"{total_earned} грн")
    col2.metric("Виплати майстрам", f"{total_master} грн")
    col3.metric("Чистий прибуток", f"{total_earned - total_master} грн")

    st.markdown("---")
    st.subheader("Детальна таблиця виконання")
    st.dataframe(app_rep, use_container_width=True)
  else:
    st.info("Недостатньо даних для звітів.")

    
