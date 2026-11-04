from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/orders/<int:order_id>")
def get_order(order_id):
    return jsonify({"id": order_id, "status": "shipped"})


if __name__ == "__main__":
    app.run(port=8080, debug=True)
