from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 50)
    print("  Janashakthi Insurance Portal")
    print("=" * 50)
    print("  Customer Portal : http://localhost:5000")
    print("  Underwriter     : http://localhost:5000/underwriter")
    print("=" * 50)
    app.run(debug=True, port=5001)
