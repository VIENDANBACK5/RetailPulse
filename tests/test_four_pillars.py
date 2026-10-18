"""
Verification test suite for all 4 advanced engineering pillars:
1. Real-time Event Streaming with Kafka Broker
2. Deep Learning Autoencoder Latent Clustering
3. Spatial Data Mining & Haversine Distance Matrix
4. Distributed Pipeline Security & HMAC-SHA256 Lake Staging
"""
import json
import os
import sys

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.streaming.kafka_engine import produce_order_event, produce_inventory_event
from src.streaming.stream_processor import stream_processor
from src.mining.spatial_optimization import compute_spatial_matrix, find_optimal_stock_transfer
from src.security.pipeline_guard import generate_hmac_signature, verify_payload_signature, SecureStagingManager


def test_pillar_1_kafka_streaming():
    initial_count = stream_processor.processed_count

    # Produce order event
    msg_order = produce_order_event(
        branch_code='HN',
        customer_code='12368',
        items=[{'sku': 'PRD-001', 'quantity': 2, 'price': 15.5}],
        total_amount=31.0
    )
    assert msg_order.topic == 'retail.orders.event'
    assert msg_order.value['total_amount'] == 31.0

    # Produce inventory update event
    msg_inv = produce_inventory_event(
        branch_code='HN',
        sku='PRD-001',
        delta=-2,
        current_stock=48,
        reason='Order placement'
    )
    assert msg_inv.topic == 'retail.inventory.event'

    # Check metrics
    metrics = stream_processor.get_dashboard_stream_metrics()
    assert metrics['processed_events'] >= initial_count + 1
    assert metrics['realtime_revenue'] >= 31.0
    print("[PASS] Pillar 1: Kafka Broker & Stream Processor working seamlessly.")


def test_pillar_2_deep_autoencoder():
    with open('models/autoencoder_eval.json', 'r', encoding='utf-8') as f:
        eval_data = json.load(f)

    # Validate model performance metrics
    assert 'autoencoder_silhouette' in eval_data
    assert 'reconstruction_mse' in eval_data
    assert eval_data['autoencoder_silhouette'] > eval_data['traditional_silhouette']
    assert eval_data['reconstruction_mse'] <= 0.02
    print(f"[PASS] Pillar 2: Autoencoder Silhouette ({eval_data['autoencoder_silhouette']:.4f}) outperforms K-Means ({eval_data['traditional_silhouette']:.4f}) with MSE Loss ({eval_data['reconstruction_mse']:.5f}).")


def test_pillar_3_spatial_optimization():
    matrix = compute_spatial_matrix()
    hn_dn = matrix['HN']['DN']
    dn_sg = matrix['DN']['SG']
    hn_sg = matrix['HN']['SG']

    # Validate Haversine distances
    assert round(hn_dn, 1) == 605.9
    assert round(dn_sg, 1) == 606.0
    assert round(hn_sg, 1) == 1137.8

    # Rebalance calculation
    current_inventory = {"HN": 65, "DN": 12, "SG": 42}
    rebalance = find_optimal_stock_transfer(
        product_sku='PRD-004',
        deficit_branch='DN',
        needed_quantity=30,
        current_inventory=current_inventory,
        safe_stock=15
    )
    assert rebalance['status'] == 'OPTIMAL_ROUTE_FOUND'
    assert rebalance['to_branch'] == 'DN'
    assert rebalance['from_branch'] == 'HN'
    print(f"[PASS] Pillar 3: Haversine distance matrix verified. Optimal transfer: {rebalance['from_branch']} -> {rebalance['to_branch']} ({rebalance['distance_km']} km, {rebalance['est_delivery_time']}).")


def test_pillar_4_pipeline_security():
    staging_mgr = SecureStagingManager()
    records = [{"order_id": 1, "sku": "PRD-001", "qty": 5}]
    payload = {
        "source_node": "SG",
        "batch_id": "BATCH-TEST-2026",
        "records_count": len(records),
        "records": records
    }

    # Generate HMAC signature
    signature = generate_hmac_signature(payload)
    assert len(signature) == 64  # SHA256 hex string length

    # Verify authentic payload
    assert verify_payload_signature(payload, signature) is True

    # Test tampering attack (changing quantity)
    tampered_records = [{"order_id": 1, "sku": "PRD-001", "qty": 9999}]
    tampered_payload = {
        "source_node": "SG",
        "batch_id": "BATCH-TEST-2026",
        "records_count": len(tampered_records),
        "records": tampered_records
    }
    assert verify_payload_signature(tampered_payload, signature) is False

    # Stage incoming batch
    success, msg = staging_mgr.stage_incoming_batch("SG", "BATCH-TEST-2026", records, signature)
    assert success is True

    # Stage tampered batch
    bad_success, bad_msg = staging_mgr.stage_incoming_batch("SG", "BATCH-TAMPER-2026", tampered_records, signature)
    assert bad_success is False
    print("[PASS] Pillar 4: HMAC-SHA256 tamper verification and isolated staging lake working as expected.")


if __name__ == '__main__':
    test_pillar_1_kafka_streaming()
    test_pillar_2_deep_autoencoder()
    test_pillar_3_spatial_optimization()
    test_pillar_4_pipeline_security()
    print("\n==========================================")
    print("ALL 4 ADVANCED PILLARS TESTED AND PASSED!")
    print("==========================================")
