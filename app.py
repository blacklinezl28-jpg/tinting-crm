from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///crm.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# --- МОДЕЛІ БАЗИ ДАНИХ ---
class Appointment(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  date = db.Column(db.String(20), nullable=False)
  time = db.Column(db.String(20), nullable=False)
  client_name = db.Column(db.String(100), nullable=False)
  client_phone = db.Column(db.String(30), nullable=False)
  car_brand = db.Column(db.String(50), nullable=False)
  car_model = db.Column(db.String(50), nullable=False)
  car_number = db.Column(db.String(30), nullable=False)
  status = db.Column(db.String(30), default="Очікує")
  final_price = db.Column(db.Float, default=0.0)


class Inventory(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  item_name = db.Column(db.String(100), nullable=False)
  category = db.Column(db.String(50), nullable=False)
  width_cm = db.Column(db.Float, default=0.0)
  meters_left = db.Column(db.Float, nullable=False)
  min_limit = db.Column(db.Float, default=5.0)
  price_usd = db.Column(db.Float, nullable=False)
  exchange_rate = db.Column(db.Float, default=41.0)
  unit = db.Column(db.String(20), default="м")

  @property
  def cost_per_unit_uah(self):
    return self.price_usd * self.exchange_rate


class Service(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  service_name = db.Column(db.String(100), nullable=False)
  default_price = db.Column(db.Float, nullable=False)


# Створення таблиць
with app.app_context():
  db.create_all()


# --- МАРШРУТИ (ROUTES) ---


@app.route("/")
def index():
  appointments = Appointment.query.all()
  return render_template("index.html", appointments=appointments)


@app.route("/appointments")
def appointments():
  appointments = Appointment.query.all()
  return render_template("reports.html", appointments=appointments, debts=[])


@app.route("/inventory")
def inventory():
  items = Inventory.query.all()
  return render_template("inventory.html", inventory=items)


@app.route("/inventory/add", methods=["POST"])
def add_inventory():
  new_item = Inventory(
      item_name=request.form["item_name"],
      category=request.form["category"],
      width_cm=float(request.form.get("width_cm", 0)),
      meters_left=float(request.form["meters_left"]),
      min_limit=float(request.form.get("min_limit", 5)),
      price_usd=float(request.form["price_usd"]),
      exchange_rate=float(request.form.get("exchange_rate", 41.0)),
      unit=request.form.get("unit", "м"),
  )
  db.session.add(new_item)
  db.session.commit()
  return redirect(url_for("inventory"))


@app.route("/services")
def services():
  all_services = Service.query.all()
  return render_template("services.html", services=all_services)


@app.route("/services/add", methods=["POST"])
def add_service():
  new_service = Service(
      service_name=request.form["service_name"],
      default_price=float(request.form["default_price"]),
  )
  db.session.add(new_service)
  db.session.commit()
  return redirect(url_for("services"))


@app.route("/services/delete/<int:id>", methods=["POST"])
def delete_service(id):
  service = Service.query.get_or_404(id)
  db.session.delete(service)
  db.session.commit()
  return redirect(url_for("services"))


@app.route("/reports")
def reports():
  all_appointments = Appointment.query.all()
  # Можна фільтрувати борги, якщо статус або оплата не пройшли
  debts = []
  return render_template(
      "reports.html", appointments=all_appointments, debts=debts
  )


@app.route("/clients")
def clients():
  # Групуємо або витягуємо унікальних клієнтів із записів
  all_clients = Appointment.query.all()
  return render_template("clients.html", clients=all_clients)


if __name__ == "__main__":
  app.run(debug=True)
