from flask import Blueprint, send_from_directory, current_app
import os

views_bp = Blueprint('views', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@views_bp.route('/')
def customer_portal():
    return send_from_directory(os.path.join(BASE_DIR, 'templates'), 'customer.html')

@views_bp.route('/underwriter')
def underwriter_portal():
    return send_from_directory(os.path.join(BASE_DIR, 'templates'), 'underwriter.html')

@views_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
