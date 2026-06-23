from revolut_app.loaders.queries import SELECT_ALL_FX_EVENTS_Q


def test_replay_query_preserves_all_events():
    normalized_query = ' '.join(SELECT_ALL_FX_EVENTS_Q.split()).upper()

    assert 'INNER JOIN GOLD.DIM_EVENT_DATASETS' in normalized_query
    assert 'ANY INNER JOIN' not in normalized_query
