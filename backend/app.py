from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from backend.config import Config
from backend.database.seed import seed_all
from backend.routes import auth, lessons, speech, translate, flashcards, doubt, worksheets, analytics, textbooks, rag, classroom, dictionary


def create_app() -> Flask:
    project_root = Path(__file__).resolve().parents[1]
    frontend_dir = project_root / "frontend"
    stitch_dir = frontend_dir / "stitch_bhashasetu_vernacular_classroom_application"

    # Serve frontend/assets/* directly under /assets/* (e.g. frontend/assets/js/api.js
    # -> /assets/js/api.js). static_folder must point AT the assets directory itself —
    # pointing it at frontend_dir (as a previous version did) double-nests the path to
    # /assets/assets/js/api.js and 404s api.js on every page that loads it (dashboard,
    # lesson-setup, live-classroom, worksheet, analytics, dictionary all silently lose
    # window.BhashaSetuAPI as a result). Page routes below use stitch_dir directly and
    # are unaffected either way.
    app = Flask(__name__, static_folder=str(frontend_dir / "assets"), static_url_path="/assets")
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    CORS(app)

    seed_all()

    app.register_blueprint(auth.bp)
    app.register_blueprint(lessons.bp)
    app.register_blueprint(speech.bp)
    app.register_blueprint(translate.bp)
    app.register_blueprint(flashcards.bp)
    app.register_blueprint(doubt.bp)
    app.register_blueprint(worksheets.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(textbooks.bp)
    app.register_blueprint(rag.bp)
    app.register_blueprint(classroom.bp)
    app.register_blueprint(dictionary.bp)

    @app.get("/")
    def index_page():
        return send_from_directory(stitch_dir / "1._teacher_login_bhashasetu", "code.html")

    @app.get("/dashboard")
    def dashboard_page():
        return send_from_directory(stitch_dir / "2._teacher_dashboard_bhashasetu", "code.html")

    @app.get("/lesson-setup")
    def lesson_setup_page():
        return send_from_directory(stitch_dir / "3._lesson_setup_bhashasetu", "code.html")

    @app.get("/live-classroom")
    def live_classroom_page():
        return send_from_directory(stitch_dir / "4._live_classroom_bhashasetu", "code.html")

    @app.get("/worksheet")
    def worksheet_page():
        return send_from_directory(stitch_dir / "5._student_worksheet_bhashasetu", "code.html")

    @app.get("/analytics")
    def analytics_page():
        return send_from_directory(stitch_dir / "6._assessment_analytics_bhashasetu", "code.html")

    @app.get("/dictionary")
    def dictionary_page():
        return send_from_directory(stitch_dir / "7._dictionary_bhashasetu", "code.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "app_mode": Config.APP_MODE})

    return app


if __name__ == "__main__":
    flask_app = create_app()
    flask_app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
