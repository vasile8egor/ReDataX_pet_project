INSERT_ROWS_Q_TEMPLATE = '''
INSERT INTO {table} ({columns}) VALUES
'''

DELETE_EXPERIMENT_Q_TEMPLATE = '''
ALTER TABLE {table}
DELETE WHERE experiment_id = '{experiment_id}'
SETTINGS mutations_sync = 1
'''

DELETE_RESEARCH_MODEL_REGISTRY_Q_TEMPLATE = '''
ALTER TABLE gold.dim_research_model_registry
DELETE WHERE model_id IN ({model_ids})
SETTINGS mutations_sync = 1
'''

DELETE_RESEARCH_POLICY_REGISTRY_Q_TEMPLATE = '''
ALTER TABLE gold.dim_research_policy_registry
DELETE WHERE policy_id IN ({policy_ids})
SETTINGS mutations_sync = 1
'''
