from flask import Flask, abort, jsonify, redirect, render_template, url_for

from analysis.preprocessing import get_dashboard_view_data, get_mineral_detail


app = Flask(__name__)


@app.template_filter("signed")
def signed(value):
    if value is None:
        return "-"
    return f"{value:+.1f}%"


@app.template_filter("number")
def number(value):
    if value is None:
        return "-"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


@app.route("/")
def index():
    return render_template("index.html", dashboard=get_dashboard_view_data())


@app.route("/mineral/<mineral_id>")
def detail(mineral_id):
    if get_mineral_detail(mineral_id) is None:
        abort(404)
    return redirect(url_for("index"))


@app.route("/news/<mineral_id>/<issue_slug>")
def news(mineral_id, issue_slug):
    abort(404)


@app.route("/api/dashboard")
def dashboard_api():
    return jsonify(get_dashboard_view_data())


@app.route("/api/mineral/<mineral_id>")
def mineral_api(mineral_id):
    mineral = get_mineral_detail(mineral_id)
    if mineral is None:
        abort(404)
    return jsonify(mineral)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True)
