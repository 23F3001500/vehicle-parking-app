from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Admin credentials
ADMIN_USERNAME = 'sneha'
ADMIN_PASSWORD = 'sneha123'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    vehicle_number = db.Column(db.String(20))

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pincode = db.Column(db.String(6), nullable=False)
    price = db.Column(db.Float, nullable=False)
    max_spots = db.Column(db.Integer, nullable=False)

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    spot_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(1), nullable=False, default='A')  # 'A' or 'O'

    lot = db.relationship('ParkingLot', backref=db.backref('spots', lazy=True))

    @property
    def active_reservation(self):
        return self.reservations.filter_by(end_time=None).order_by(Reservation.start_time.desc()).first()

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    cost = db.Column(db.Float, nullable=True)

    spot = db.relationship('ParkingSpot', backref='reservations')
    user = db.relationship('User', backref='reservations')


@app.before_request
def create_tables_once():
    if not hasattr(app, 'db_initialized'):
        db.create_all()
        app.db_initialized = True

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        vehicle_number = request.form['vehicle_number']  # Get vehicle number from form

        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))

        # Create and add new user
        user = User(username=username, password=password, vehicle_number=vehicle_number)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    session.clear()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['admin'] = False
            return redirect(url_for('user_dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    lots = ParkingLot.query.all()

    lot_statuses = []
    for lot in lots:
        total_spots = len(lot.spots)
        available_spots = sum(1 for spot in lot.spots if spot.status == 'A')
        occupied_spots = total_spots - available_spots
        lot_statuses.append({
            'lot': lot,
            'total_spots': total_spots,
            'available_spots': available_spots,
            'occupied_spots': occupied_spots,
        })
    return render_template('admin_dashboard.html', lots=lots,lot_statuses=lot_statuses,zip=zip)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['admin_username'] == ADMIN_USERNAME and request.form['admin_password'] == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/create_parking_lot', methods=['GET', 'POST'])
def create_parking_lot():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        pincode = request.form.get('pincode', '').strip()
        price_str = request.form.get('price', '').strip()
        num_spots_str = request.form.get('num_spots', '').strip()

        # Basic validation
        if not name or not address or not pincode or not price_str or not num_spots_str:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for('create_parking_lot'))

        try:
            price = float(price_str)
            num_spots = int(num_spots_str)
        except ValueError:
            flash("Price must be a number and number of spots must be an integer.", "danger")
            return redirect(url_for('create_parking_lot'))

        # Create the new lot
        new_lot = ParkingLot(
            name=name,
            address=address,
            pincode=pincode,
            price=price,
            max_spots=num_spots
        )
        db.session.add(new_lot)
        db.session.commit()

        # Add parking spots
        for i in range(1, num_spots + 1):
            spot = ParkingSpot(lot_id=new_lot.id, spot_number=i, status='A')
            db.session.add(spot)

        db.session.commit()
        flash('Parking lot and spots created successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('create_parking_lot.html')


@app.route('/admin/users')
def view_users():
    users = User.query.all()
    return render_template('view_users.html', users=users)



@app.route('/user_dashboard')
def user_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    user = User.query.get(user_id)

    # Only fetch reservations that are still active (i.e., end_time is None)
    active_reservations = Reservation.query.filter_by(
        user_id=user.id,
        end_time=None
    ).order_by(Reservation.start_time.desc()).all()

    return render_template('user_dashboard.html', user=user, reservations=active_reservations)

@app.route('/lots')
def view_lots():
    lots = ParkingLot.query.all()
    return render_template('lots.html', lots=lots)

@app.route('/lot/<int:lot_id>')
def view_parking_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()
    return render_template('lot_details.html', lot=lot, spots=spots)

@app.route('/book/<int:spot_id>')
def book_spot(spot_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    spot = ParkingSpot.query.get_or_404(spot_id)
    if spot.status == 'A':
        spot.status = 'O'
        reservation = Reservation(spot_id=spot.id, user_id=session['user_id'])
        db.session.add(reservation)
        db.session.commit()
        flash('Spot successfully booked!', 'success')
    else:
        flash('Spot already occupied!', 'danger')
    return redirect(url_for('view_parking_lot', lot_id=spot.lot_id))

@app.route('/reservations')
def view_reservations():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('view_reservations.html', reservations=user.reservations)

@app.route('/admin/edit-lot/<int:lot_id>', methods=['GET', 'POST'])
def edit_parking_lot(lot_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    lot = ParkingLot.query.get_or_404(lot_id)

    if request.method == 'POST':
        # Update lot details from form data
        lot.name = request.form['name']
        lot.address = request.form['address']
        lot.pincode = request.form['pincode']
        lot.price = float(request.form['price'])
        lot.max_spots = int(request.form['max_spots'])

        db.session.commit()
        flash('Parking lot updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    # GET request: show edit form with current lot data
    return render_template('edit_parking_lot.html', lot=lot)

@app.route('/admin/delete-lot/<int:lot_id>', methods=['POST'])
def delete_parking_lot(lot_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    lot = ParkingLot.query.get_or_404(lot_id)
    occupied_or_reserved = any(spot.status != 'A' for spot in lot.spots)
    if occupied_or_reserved:
        flash('Cannot delete this lot. Some spots are reserved or occupied.', 'danger')
        return redirect(url_for('admin_dashboard'))

    # Delete all spots linked to this lot first (to avoid foreign key issues)
    ParkingSpot.query.filter_by(lot_id=lot.id).delete()
    db.session.delete(lot)
    db.session.commit()
    flash('Parking lot deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/spot_status/<int:spot_id>', methods=['POST'])
def spot_status(spot_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    spot = ParkingSpot.query.get_or_404(spot_id)
    new_status = request.form.get('new_status')

    if new_status == 'O' and spot.status == 'A':
        # Mark spot as occupied and create new reservation
        spot.status = 'O'
        db.session.commit()
        flash("Spot marked as Occupied.", "info")

    elif new_status == 'R' and spot.status == 'O':
        # Mark spot as available and end the latest reservation
        spot.status = 'A'

        latest_reservation = Reservation.query.filter_by(
            spot_id=spot_id,
            user_id=session['user_id']
        ).order_by(Reservation.id.desc()).first()

        if latest_reservation and not latest_reservation.end_time:
            latest_reservation.end_time = datetime.utcnow()
            duration = (latest_reservation.end_time - latest_reservation.start_time).total_seconds() / 3600
            latest_reservation.cost = round(duration * spot.lot.price, 2)

        db.session.commit()
        flash("Spot released and reservation ended.", "success")

    else:
        flash("Invalid status change.", "warning")

    if session.get('admin'):
        return redirect(url_for('view_spot_status'))  # only for admin
    else:
        return redirect(url_for('user_dashboard'))    # regular user




@app.route('/reserve', methods=['GET', 'POST'])
def reserve_spot():
    if 'user_id' not in session:
        flash("Please login to reserve a spot.", "warning")
        return redirect(url_for('login'))

    lots = ParkingLot.query.join(ParkingSpot).filter(ParkingSpot.status == 'A').all()

    if request.method == 'POST':
        lot_id = request.form['lot_id']
        user_id = session['user_id']

        # Find first available spot in that lot
        spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()

        if spot:
            # Don't change status now; let user click 'Occupied' themselves
            reservation = Reservation(user_id=user_id, spot_id=spot.id)
            db.session.add(reservation)
            db.session.commit()
            flash(f"Spot {spot.spot_number} in lot {spot.lot.name} reserved successfully!", "success")
        else:
            flash("No available spots in the selected lot.", "danger")

        return redirect(url_for('user_dashboard'))

    return render_template('reserve.html', lots=lots)




@app.route('/admin/view-spot-status')
def view_spot_status():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))  
    # or 403 Forbidden
    lot_id = request.args.get('lot_id')
    lots = ParkingLot.query.all()
    selected_lot = ParkingLot.query.get(lot_id) if lot_id else None

    return render_template('view_spot_status.html', lots=lots, selected_lot=selected_lot)

@app.route('/admin/view-occupant/<int:spot_id>')
def view_occupant_details(spot_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    spot = ParkingSpot.query.get_or_404(spot_id)
    lot_id = spot.lot_id

    reservation = Reservation.query.filter_by(spot_id=spot_id, end_time=None).first()
    if reservation:
        user = reservation.user
    else:
        user = None

    return render_template('occupant_details.html', user=user, reservation=reservation, lot_id=lot_id)
     
 



@app.route('/user_summary')
def user_summary():
    # Query all parking lots
    lots = ParkingLot.query.all()

    # Prepare data for total spots chart
    lot_names = [lot.name for lot in lots]
    total_spots = [len(lot.spots) for lot in lots]

    lot_chart_data = {
        'labels': lot_names,
        'data': total_spots
    }

    # Prepare data for parking spot status chart (aggregated over all lots)
    # Count number of spots with status = 'O' (Occupied), 'A' (Available), 'R' (Reserved)
    occupied_count = ParkingSpot.query.filter_by(status='O').count()
    available_count = ParkingSpot.query.filter_by(status='A').count()
    reserved_count = ParkingSpot.query.filter_by(status='R').count()

    status_chart_data = {
        'labels': ['Occupied', 'Available'],
        'data': [occupied_count, available_count]
    }

    return render_template(
        'user_summary.html',
        lot_chart_data=lot_chart_data,
        status_chart_data=status_chart_data
    )


@app.route('/admin/users')
def admin_users():
    users = User.query.all()  # get all users from DB
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if user:
        # Delete reservations first
        Reservation.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.username} deleted successfully', 'success')
    else:
        flash('User not found', 'error')
    return redirect(url_for('admin_users'))

# Example route
@app.route('/admin/summary-charts')
def admin_summary():
    parking_lots = ParkingLot.query.all()

    lot_names = []
    total_spots = []
    occupied_spots = []
    booked_spots = []
    available_spots = []

    total_occupied = 0
    total_booked = 0
    total_available = 0

    for lot in parking_lots:
        lot_names.append(lot.name)
        spots = lot.spots

        total = len(spots)
        occupied = len([s for s in spots if s.status == 'O'])
        available= len([s for s in spots if s.status == 'A'])
        booked= len([s for s in spots if s.status == 'R'])

        total_spots.append(total)
        occupied_spots.append(occupied)
        booked_spots.append(booked)
        available_spots.append(available)

        total_occupied += occupied
        total_booked += booked
        total_available += available

    return render_template(
        'admin_summary.html',
        lot_names=lot_names,
        total_spots=total_spots,
        occupied_spots=occupied_spots,
        booked_spots=booked_spots,
        available_spots=available_spots,
        total_occupied=total_occupied,
        total_booked=total_booked,
        total_available=total_available
    )

#with app.app_context():
    #db.create_all()

if __name__ == '__main__':
    app.run(debug=True)