from flask import Blueprint, request, jsonify, current_app

from app.services.request_service import (
    get_requests_by_status,
    get_request_detail,
    process_decision,
    get_stats,
)
from app.utils.helpers import success, error

underwriter_bp = Blueprint('underwriter', __name__)


@underwriter_bp.route('/requests', methods=['GET'])
def list_requests():
    status = request.args.get('status', 'Under Review')
    requests_list = get_requests_by_status(current_app.config['DATABASE_PATH'], status)
    return jsonify(success({"requests": requests_list}))


@underwriter_bp.route('/request/<request_id>', methods=['GET'])
def request_detail(request_id):
    req, docs = get_request_detail(current_app.config['DATABASE_PATH'], request_id)
    if not req:
        return jsonify(error("Request not found.")), 404
    return jsonify(success({"request": req, "documents": docs}))


@underwriter_bp.route('/decide', methods=['POST'])
def decide():
    data      = request.get_json()
    request_id = data.get('request_id')
    decision  = data.get('decision')
    notes     = data.get('notes', '')
    new_value = data.get('new_value')

    if not request_id or decision not in ('Approved', 'Rejected'):
        return jsonify(error("request_id and a valid decision (Approved/Rejected) are required.")), 400

    ok, message = process_decision(
        current_app.config['DATABASE_PATH'],
        request_id, decision, notes, new_value
    )

    if ok:
        return jsonify(success({"message": message}))
    return jsonify(error(message))


@underwriter_bp.route('/stats', methods=['GET'])
def stats():
    data = get_stats(current_app.config['DATABASE_PATH'])
    return jsonify(success({"stats": data}))
