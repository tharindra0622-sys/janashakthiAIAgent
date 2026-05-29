from flask import Blueprint, request, jsonify, current_app

from app.services.customer_service import find_customer
from app.services.ai_service import chat_with_customer
from app.services.request_service import create_request, submit_request
from app.services.otp_service import generate_otp, verify_otp, send_otp_email, mask_email
from app.models.constants import SERVICE_REQUIREMENTS
from app.utils.helpers import success, error

customer_bp = Blueprint('customer', __name__)


@customer_bp.route('/identify', methods=['POST'])
def identify():
    data = request.get_json()
    nic = (data.get('nic') or '').strip()
    policy_number = (data.get('policy_number') or '').strip()

    if not nic and not policy_number:
        return jsonify(error("Please provide your NIC or Policy Number.")), 400

    customer = find_customer(
        current_app.config['DATABASE_PATH'],
        nic=nic,
        policy_number=policy_number
    )

    if not customer:
        return jsonify(error("Customer not found. Please check your NIC or Policy Number."))

    return jsonify(success({"customer": customer}))


# ── Step 1 of 2-FA: send OTP to registered email ────────────────────────────
@customer_bp.route('/send-otp', methods=['POST'])
def send_otp():
    data          = request.get_json()
    customer_id   = (data.get('customer_id') or '').strip()
    customer_email = (data.get('email') or '').strip()
    customer_name  = (data.get('full_name') or 'Customer').strip()

    if not customer_id or not customer_email:
        return jsonify(error("Missing customer_id or email.")), 400

    otp = generate_otp(
        customer_id,
        expiry_seconds=current_app.config.get('OTP_EXPIRY_SECONDS', 300)
    )

    sent, err_msg = send_otp_email(
        to_email=customer_email,
        otp=otp,
        customer_name=customer_name,
        mail_user=current_app.config['MAIL_USERNAME'],
        mail_password=current_app.config['MAIL_PASSWORD'],
        mail_server=current_app.config.get('MAIL_SERVER', 'smtp.gmail.com'),
        mail_port=current_app.config.get('MAIL_PORT', 587)
    )

    if sent:
        return jsonify(success({
            "message":      "OTP sent successfully.",
            "masked_email": mask_email(customer_email)
        }))

    return jsonify(error(f"Could not send OTP. {err_msg}")), 500


# ── Step 2 of 2-FA: verify the OTP entered by customer ──────────────────────
@customer_bp.route('/verify-otp', methods=['POST'])
def check_otp():
    data        = request.get_json()
    customer_id = (data.get('customer_id') or '').strip()
    otp_input   = (data.get('otp') or '').strip()

    if not customer_id or not otp_input:
        return jsonify(error("Missing customer_id or otp.")), 400

    ok, reason = verify_otp(customer_id, otp_input)

    if ok:
        return jsonify(success({"verified": True, "message": "Identity verified."}))

    return jsonify(error(reason))


@customer_bp.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '')
    session_data = data.get('session', {})
    customer = data.get('customer', {})

    reply = chat_with_customer(
        message=message,
        customer=customer,
        session_data=session_data,
        api_key=current_app.config['GROQ_API_KEY'],
        model_name=current_app.config['GROQ_MODEL']
    )

    return jsonify(success({"reply": reply}))


@customer_bp.route('/request/create', methods=['POST'])
def create():
    data = request.get_json()
    customer_id   = data.get('customer_id')
    policy_number = data.get('policy_number')
    service_type  = data.get('service_type')

    if not all([customer_id, policy_number, service_type]):
        return jsonify(error("Missing required fields: customer_id, policy_number, service_type.")), 400

    request_id   = create_request(
        current_app.config['DATABASE_PATH'],
        customer_id, policy_number, service_type
    )
    requirements = SERVICE_REQUIREMENTS.get(service_type, {})

    return jsonify(success({
        "request_id":   request_id,
        "requirements": requirements,
    }))


@customer_bp.route('/request/submit', methods=['POST'])
def submit():
    data = request.get_json()
    request_id = data.get('request_id')

    if not request_id:
        return jsonify(error("request_id is required.")), 400

    ok, message = submit_request(current_app.config['DATABASE_PATH'], request_id)

    if ok:
        return jsonify(success({"message": message}))
    return jsonify(error(message))
