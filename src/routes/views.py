import os
from flask import Blueprint, render_template, send_file
from src.config import BASE_DIR

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
@views_bp.route("/<slug>")
def index(slug=None):
    return render_template("index.html")

