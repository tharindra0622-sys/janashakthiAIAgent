import json
import uuid
from flask import Blueprint, request, jsonify, current_app
from app.services.ai_service import verify_document
from app.models.database import db_connection
from app.utils.helpers import allowed_file, save_uploaded_file, success, error

documents_bp = Blueprint('documents', __name__)

@documents_bp.route('/document/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify(error("No file provided.")), 400
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify(error("No file selected.")), 400
    if not allowed_file(file.filename):
        return jsonify(error("File type not allowed. Please upload PDF, JPG, or PNG.")), 400

    doc_type      = request.form.get('doc_type', 'unknown')
    request_id    = request.form.get('request_id', '')
    policy_number = request.form.get('policy_number', '')
    customer_nic  = request.form.get('customer_nic', '')

    file_path = save_uploaded_file(file, current_app.config['UPLOAD_FOLDER'], request_id, doc_type)

    ai_result = verify_document(
        file_path=file_path, doc_type=doc_type,
        policy_number=policy_number, customer_nic=customer_nic,
        api_key=current_app.config['GROQ_API_KEY'],
        model_name=current_app.config['GROQ_MODEL']
    )

    doc_id = str(uuid.uuid4())[:8].upper()
    with db_connection(current_app.config['DATABASE_PATH']) as db:
        db.execute(
            'INSERT INTO documents (id, request_id, doc_type, file_path, ai_verified, ai_feedback) VALUES (?,?,?,?,?,?)',
            (doc_id, request_id, doc_type, file_path,
             1 if ai_result.get('verified') else 0, json.dumps(ai_result))
        )

    response_data = {
        "doc_id":      doc_id,
        "ai_verified": ai_result.get('verified', False),
        "feedback":    ai_result.get('feedback', ''),
        "issues":      ai_result.get('issues', []),
        "confidence":  ai_result.get('confidence', 0),
    }
    if ai_result.get('identity_data'):
        response_data['identity_data'] = ai_result['identity_data']

    return jsonify(success(response_data))
