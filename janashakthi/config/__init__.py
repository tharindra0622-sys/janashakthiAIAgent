import os
from flask import Flask
from flask_cors import CORS
from config.settings import config
from app.models.database import init_db


def create_app(env='development'):
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    )

    # Load config
    app.config.from_object(config[env])

    # Extensions
    CORS(app)

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)

    # Init database
    with app.app_context():
        init_db(app.config['DATABASE_PATH'])

    # Register blueprints
    from app.routes.customer import customer_bp
    from app.routes.underwriter import underwriter_bp
    from app.routes.documents import documents_bp
    from app.routes.views import views_bp

    app.register_blueprint(views_bp)
    app.register_blueprint(customer_bp, url_prefix='/api')
    app.register_blueprint(underwriter_bp, url_prefix='/api/underwriter')
    app.register_blueprint(documents_bp, url_prefix='/api')

    return app
