class SquareZoho:
    def __init__(self, van_driver):
        self.aws = zohoapi.get_aws_token()
        self.square = zohoapi.get_s3_file(self.aws['AWS_KEY'],self.aws['SECRET_KEY'], 'square_dict2.json')
        self.square_df = json_normalize(self.square)
        self.square_df['item_id'] = self.square_df['item_id'].astype(str)
        self.zoho_token = zohoapi.get_s3_file(self.aws['AWS_KEY'],self.aws['SECRET_KEY'], 'zoho_token.json')
        self.van = van_driver
        self.vans = {
            'mauricio':'BSPQ7V58MGQSX',
            'oscar':'EJCQ7FPG2M4BE',
            'isaac':'WZFB97FSPZ0MF',
            'ely':'EW06SGK17B6DH',
            'eduardo':'DDG5MMMHXCJSA',
            }
        self.van_id = {
            'BSPQ7V58MGQSX': {'pwh': 1729377000000087009,'cxid': 1729377000003663083, 'whid': 1729377000062698538, 'pfix': 'MAU'},
            'EJCQ7FPG2M4BE': {'pwh': 1729377000000087009,'cxid': 1729377000062689580, 'whid': 1729377000062698542, 'pfix': 'OSC'},
            'WZFB97FSPZ0MF': {'pwh': 1729377000000087011,'cxid': 1729377000003663070, 'whid': 1729377000062698546, 'pfix': 'ISA'},
            'EW06SGK17B6DH': {'pwh': 1729377000000087011,'cxid': 1729377000040623610, 'whid': 1729377000043236430, 'pfix': 'ELY'},
            'DDG5MMMHXCJSA': {'pwh': 1729377000000087011,'cxid': 1729377000041250719, 'whid': 1729377000043236426, 'pfix': 'EDU'},
        }

    def get_square_data(self):
        self.api_instance = Client(access_token=self.zoho_token['SQUARE_KEY'])
        self.body = {
            'location_ids': [self.vans[self.van]],
            'query': {
                'filter': {'date_time_filter': {'created_at': {
                    'start_at': dt.datetime.today().strftime('%Y-%m-%d'),
                    'end_at': (dt.datetime.today() + dt.timedelta(days=1)).strftime('%Y-%m-%d')
                    }

                                                }
                          }
                    },
            'return_entries': False,
            }
        self.api_response = self.api_instance.orders.search_orders(self.body)
        return json.loads(self.api_response.text)

    def remove_return_orders(self,lst, key):
        result = []
        for i, dic in enumerate(lst):
            try:
                if len(dic[key]) > 0:
                    result.append(dic)
            except:
                pass #we can use this in the future to get the returns
        return result

    def validated_data(self, json_data):
        if len(json_data) != 0:
            dta_tenders = json_normalize(json_data,'tenders',['id'],meta_prefix = 'order_')
            dta_items = json_normalize(json_data,'line_items',['id'],meta_prefix = 'order_')
            data_full = dta_tenders.merge(dta_items,how = 'left',on = ['order_id'])
            data_full = data_full.fillna(0)
            data_full['quantity'] = data_full['quantity'].astype(int)
            return data_full
        return 0

    def merge_data(self, df):
        df = df.merge(self.square_df, how='left', left_on='catalog_object_id', right_on='token')
        df.loc[df['catalog_object_id']==0,'item_id'] = '1729377000002073265'
        df.loc[df['catalog_object_id']==0,'qt'] = 1
        df.loc[df['catalog_object_id']==0,'cat'] = 'ZZZ'
        df['item_id'].fillna(0, inplace=True)
        df['qty'] = df['quantity'] * df['qt']
        df['item_total'] = df['gross_sales_money.amount'] / (107 * df['qty'])
        df['discount'] = df['total_discount_money.amount'] / 107
        df['money'] = df['total_money.amount'] / 107
        df['cat2'] = np.where(df['cat']=='ZZZ',1,0)
        df['subtotal'] = df['item_total'] * df['qty']
        df['payment'] = np.where(df['processing_fee_money.amount'] > 0, 'CARD', 'CASH')
        df['created_at'] = df['created_at'].apply(lambda x: parser.parse(str(x)).strftime('%Y-%m-%d'))

        v1 = df.loc[df['item_id']==0]['catalog_object_id'].to_list()

        return df, v1

    def create_dfs(self, df):

        try:
            df1 = df.drop_duplicates(subset=['transaction_id','catalog_object_id','gross_sales_money.amount','note'])
        except:
            df1 = df.drop_duplicates(subset=['transaction_id','catalog_object_id','gross_sales_money.amount'])

        df2 = df1.groupby(['created_at', 'location_id', 'cat', 'item_id'], as_index=False).agg({
        'subtotal': sum,
        'discount': sum,
        'qty': sum})

        df2['price'] = df2['subtotal'] / df2['qty']

        df3 = df.groupby(['payment','cat2'], as_index=False).agg({'money': sum})
        df3.cat2 = df3.cat2.astype(str)
        df3.money = df3.money * 1.07

        return df1, df2, df3

    def payment_const(self):
        try:
            cashp = '$' + str(df3.loc[(df3.payment=='CASH') & (df3.cat2=='1')].money.values[0]) + ' pending'
        except:
            cashp = 'Full Amount'

        try:
            ccp = '$' + str(df3.loc[(df3['payment']=='CARD') & (df3['cat2']=='1')].money.values[0]) + ' pending'
        except:
            ccp = 'Full Amount'

        try:
            cash0 = df3.loc[(df3.payment=='CASH') & (df3.cat2=='0')].money.values[0]
        except:
            cash0 = 0

        try:
            cc0 = df3.loc[(df3.payment=='CARD') & (df3.cat2=='0')].money.values[0]
        except:
            cc0 = 0
        return cashp, ccp, cash0, cc0

    def create_so(self, zoho, df):
        line_items = []

        for i in range(len(df)):
            line = {
            'item_id': int(df.item_id[i]),
            'rate': df.price[i],
            'discount': df.discount[i],
            'discount_type': 'item_level',
            'quantity': int(df.qty[i]),
            'warehouse_id': self.van_id[df.location_id[i]]['whid'],
            }
            line_items.append(line)

        so = parser.parse(df.created_at[0]).strftime('%y%m%d')

        data = {
        'customer_id': int(self.van_id[df.location_id[0]]['cxid']),
        'salesorder_number': self.van_id[df.location_id[0]]['pfix'] + '-' + so,
        'date': parser.parse(df.created_at[len(df)-1]).strftime('%Y-%m-%d'),
        'line_items': line_items,
        'custom_fields': [{'customfield_id': '1729377000039969865', 'value':'Square'}],
        }

        return zoho.create_order(data)

    def create_package(self, zoho, r):
        pk_items = []
        for i in range(len(r['salesorder']['line_items'])):
            if r['salesorder']['line_items'][i]['item_id'] != '1729377000002073265':
                pk_line = {'so_line_item_id': r['salesorder']['line_items'][i]['line_item_id'],
                       'quantity': r['salesorder']['line_items'][i]['quantity']
                      }
                pk_items.append(pk_line)

        pk_data = {
            'date': r['salesorder']['date'],
            'line_items': pk_items,
            }
        return zoho.create_package(r['salesorder']['salesorder_id'], pk_data)

    def shipment(self, zoho, r):
        shdata = {
        'shipment_number': r['package']['salesorder_number'],
        'date': r['package']['salesorder_date'],
        'delivery_method': 'Van',
        'tracking_number': '',
        }
        return zoho.create_shipment(r['package']['package_id'], r['package']['salesorder_id'], shdata, True)

    def delivered(self, zoho, r):
        return zoho.delivered(r['shipmentorder']['shipment_id'])

    def rounding(self, zoho, r, df):
        so = parser.parse(df.created_at[0]).strftime('%y%m%d')
        data = {
        'customer_id': int(self.van_id[df.location_id[0]]['cxid']),
        'salesorder_number': self.van_id[df.location_id[0]]['pfix'] + '-' + so,
        'date': parser.parse(df.created_at[len(df)-1]).strftime('%Y-%m-%d'),
        'adjustment': round(r['salesorder']['total'],0)-r['salesorder']['total'],
        'adjustment_description': 'Rounding'
        }
        return zoho.update_order(r['salesorder']['salesorder_id'], data)

    def create_invoice(self, zoho, r, df):
        inv_items = []
        for i in range(len(r['salesorder']['line_items'])):
            if r['salesorder']['line_items'][i]['item_id'] != '1729377000002073265':
                inv_line = {'salesorder_item_id': r['salesorder']['line_items'][i]['line_item_id'],
                           'item_id': r['salesorder']['line_items'][i]['item_id'],
                           'quantity': r['salesorder']['line_items'][i]['quantity'],
                           'discount': r['salesorder']['line_items'][i]['discount'],
                           'discount_type': 'item_level',
                           'warehouse_id': self.van_id[df.location_id[0]]['whid'],
                           'rate': r['salesorder']['line_items'][i]['rate'],
                      }
                inv_items.append(inv_line)
        inv_data = {
        'customer_id': r['salesorder']['customer_id'],
        'date': r['salesorder']['date'],
        'line_items': inv_items,
        'adjustment': r['salesorder']['adjustment'],
        'adjustment_description': r['salesorder']['adjustment_description'],
        }
        return zoho.create_invoice(inv_data)

    def create_payment(self, zoho, r, invoice_id, cash0, cashp, cc0, ccp):
        pay_data = [{
        'customer_id': r['salesorder']['customer_id'],
        'payment_mode': 'Cash',
        'amount': cash0,
        'date': r['salesorder']['date'],
        'reference_number': cashp,
        'invoices': [{
            'invoice_id': invoice_id,
            'amount_applied': cash0,
        }],
        'account_id': 1729377000028708216,
        },
        {
        'customer_id': r1['salesorder']['customer_id'],
        'payment_mode': 'Credit Card',
        'amount': cc0,
        'date': r1['salesorder']['date'],
        'reference_number': ccp,
        'invoices': [{
            'invoice_id': invoice_id,
            'amount_applied': cc0,
        }],
        'account_id': 1729377000028708190,
        }]

        if cash0 * cc0 == 0:
            if cash == 0:
                return zoho.create_cxpayment(pay_data[1])
            return zoho.create_cxpayment(pay_data[0])
        for i in range(2):
            res = zoho.create_cxpayment(pay_data[i])
        return res

    def transfer_order(self, zoho, r, df):
        so = parser.parse(df.created_at[0]).strftime('%y%m%d')
        transfer_items = []

        for i in range(len(r['salesorder']['line_items'])):
            tf_items = {
            'item_id': r['salesorder']['line_items'][i]['item_id'],
            'name': r['salesorder']['line_items'][i]['name'],
            'description': r['salesorder']['line_items'][i]['description'],
            'quantity_transfer': r['salesorder']['line_items'][i]['quantity'],
            }
            transfer_items.append(tf_items)

        transfer_data = {
        'transfer_order_number': self.van_id[df.location_id[0]]['pfix'] + '-' + so,
        'date': r['salesorder']['date'],
        'from_warehouse_id': self.van_id[df.location_id[0]]['pwh'],
        'to_warehouse_id': self.van_id[df.location_id[0]]['whid'],
        'line_items': transfer_items,
        'is_intransit_order': True,
        }

        return zoho.transfer_order(transfer_data)
