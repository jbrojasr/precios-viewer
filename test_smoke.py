from app import app, parse_workbook, DB_PATH

source = "/opt/data/cache/documents/doc_9c76a6079071_Existencias.xlsx"
products, errors, sheet = parse_workbook(source)
assert len(products) == 921, len(products)
assert not errors, errors
assert sheet == "Hoja1", sheet

with app.test_client() as client:
    health = client.get("/health")
    assert health.status_code == 200
    stats = client.get("/api/stats").get_json()
    assert stats["count"] == 921, stats
    result = client.get("/api/products?q=2008-0003&limit=1").get_json()
    assert result["count"] == 1, result
    item = result["items"][0]
    assert "cost" in item and "price" not in item, item
    assert abs(item["cost"] - 18.7804) < 0.000001, item
    page = client.get("/").get_data(as_text=True)
    assert "marginSlider" in page
    assert "Costo" in page and "Venta +30%" in page

print(f"OK: {len(products)} productos; costo={item['cost']}; venta30={item['cost'] * 1.30:.4f}; db={DB_PATH}")
