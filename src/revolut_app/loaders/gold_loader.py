from clickhouse_driver import Client


class GoldLayerLoader:
    def __init__(self, ch_host='clickhouse'):
        self.ch_client = Client(
            host=ch_host,
            port=8123,
            user='default',
            password=''
        )

    def load_transactions(self, dataframe):
        if dataframe.empty:
            return "No data to load"

        dataframe = dataframe.fillna("")

        data = dataframe.to_dict('records')
        self.ch_client.execute(
            '''
            INSERT INTO gold.fact_transactions 
            (transaction_id, account_id, booking_datetime, amount, currency, merchant_name) 
            VALUES
            ''',
            data
        )
        return f"Successfully loaded {len(data)} rows"
