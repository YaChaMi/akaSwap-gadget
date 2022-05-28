from flask import Flask, render_template, request, flash
from pyecharts import options as opts
from pyecharts.charts import Line, Pie
from jinja2 import Markup
import os
import json
import requests
from datetime import datetime, timedelta
import statistics

# Platform to contract
contracts = {
    'akaobj' : 'KT1AFq5XorPduoYyWxs5gEyrFK6fVjJVbtCj',
    'asmeir' : 'KT1VTBuWpY5f4sEdCHVWRSn99yUS5HqVWVk2',
    'tezdozen' : 'KT1Xphnv7A1sUgRwZsecmAGFWm7WNxJz76ax',
    'td-guardian' : 'KT1ShjqosdcqJBhaabPvkCwoXtS1R2dEbx4W',
    'hicetnunc' : 'KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton'
}

# Contract to platform
platforms = {
    'KT1AFq5XorPduoYyWxs5gEyrFK6fVjJVbtCj' : ['akaSwap','akaobj'],
    'KT1VTBuWpY5f4sEdCHVWRSn99yUS5HqVWVk2' : ['ASMeiR','asmeir'],
    'KT1Xphnv7A1sUgRwZsecmAGFWm7WNxJz76ax' : ['Tez Dozen','tezdozen'],
    'KT1ShjqosdcqJBhaabPvkCwoXtS1R2dEbx4W' : ['TD-Guardian','td-guardian'],
    'KT1RJ6PbjHpwc3M5rw5s2Nbmefwbuwbdxton' : ['Hicetnunc','hicetnunc']
}

# Type to actions
types = {
    'general' : ['mint','sell','burn','transfer','collect','swap','cancel_swap','make_offer','sell_offer','collect_offer'],
    'gacha' : ['make_gacha','sell_gacha','collect_gacha'],
    'auction' : ['make_auction','sell_auction','collect_auction'],
    'bundle' : ['make_bundle','sell_bundle','collect_bundle']
}

# Error
class Error(Exception):
    def __init__(self, msg):
        self.msg = msg

# Find alias of address
def find_alias(addr):
    r = requests.request("GET", f"https://api.tzkt.io/v1/accounts/{addr}")
    alias = json.loads(r.text)['alias']
    return alias if alias != None else addr

# Give token id and contract to find token
def find_token(token_id,contract):

    r = requests.request("GET", f"https://api.akaswap.com/v2/fa2tokens/{contract}/{token_id}")
    if r.status_code != 200:
        raise Error('Non-existent Token')

    token = json.loads(r.text)    
    return token

# Find price history of token
def token_price_history(token_id,platform):

    current_time = datetime.now()

    contract = contracts[platform]

    try:
        token = find_token(token_id,contract)
    except Exception as e:
        flash(e.msg, 'danger')
        return

    # Modify display uri
    photo = token['displayUri']
    if photo == None:
        flash('Non-existent Photo', 'warning')
    else:
        photo = photo.replace("ipfs://", "https://ipfs.io/ipfs/")

    # Find the minimum sale price
    min_sale = float('inf')
    for sale in token['sale']['swaps']:
        sale_xtz = sale['xtzPerToken'] / 1000000
        min_sale = sale_xtz if sale_xtz < min_sale else min_sale

    # Use contract and token id to find transaction records
    r = requests.request("GET", f"https://akaswap.com/api/v2/fa2tokens/{contract}/{token_id}/records")
    record_list = json.loads(r.text)['records']
    aggr_price = 0
    timestamps, prices, avg_prices = [], [], []
    for record in reversed(record_list):
        if record['type'] in ['collect_offer','collect']:
            timestamps.append(datetime.strptime(record['timestamp'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8))
            prices.append(record['price'] / 1000000)
            aggr_price += record['price'] / 1000000
            avg_prices.append(round(aggr_price / len(prices),2))

    # Plot price history
    txn_num = len(prices)
    if prices:
        mean_price = statistics.mean(prices)
        max_price , min_price = max(prices) , min(prices)
        chart = Line()
        chart.add_xaxis(timestamps)
        chart.add_yaxis("History Transaction Price",prices,label_opts=opts.LabelOpts(is_show=False), color='rgba(255, 151, 151, 0.8)', linestyle_opts=opts.LineStyleOpts(width=3))
        chart.add_yaxis("Time-based Average Transaction Price",avg_prices,label_opts=opts.LabelOpts(is_show=False), color='rgba(255, 208, 151, 0.8)', linestyle_opts=opts.LineStyleOpts(width=1))
        chart.set_global_opts(title_opts=opts.TitleOpts(title="Price History"),xaxis_opts=opts.AxisOpts(name='Time',type_="time"),yaxis_opts=opts.AxisOpts(name='Price (xtz)'))
        if min_sale != float('inf'):
            chart.set_series_opts(markline_opts=opts.MarkLineOpts(data=[opts.MarkLineItem(y=min_sale, name="Current Min Sale Price",type_='min')] , linestyle_opts=opts.LineStyleOpts(color='rgba(150, 226, 255, 0.8)',type_='dotted')))
        chart = Markup(chart.render_embed())
    else:
        flash('Non-existent Price History', 'warning')

    # Plot owner
    owners = token['owners']
    if owners:
        if token.get('ownerAliases'):
            for addr, name in token['ownerAliases'].items():
                if name:
                    owners[name] = owners.pop(addr)
        pie = Pie()
        pie.add('', [list(item) for item in owners.items()])
        pie.set_global_opts(title_opts=opts.TitleOpts(title="Owners"),legend_opts=opts.LegendOpts(is_show=False))
        pie.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
        pie = Markup(pie.render_embed())
    else:
        flash('Non-existent Owner', 'warning')
    
    # Set token data
    token_data = {
        'Token Name' : token['name'],
        'Photo' : photo,
        'Chart' : chart if prices else None,
        'Pie' : pie if owners else None,
        'Current Time' : current_time.strftime("%Y-%m-%d %H:%M:%S"),
        'URL' : f'https://akaswap.com/{platform}/{token_id}',
        'info' : {
            'Token ID' : token_id,
            'Amount'   : token['amount'],
            'Total Transaction Number' : txn_num,
            'Max Transaction Price'    : "{:.2f} xtz".format(max_price) if prices else '',
            'Mean Transaction Price'   : "{:.2f} xtz".format(mean_price) if prices else '',
            'Min Transaction Price'    : "{:.2f} xtz".format(min_price) if prices else '',
            'Current Min Sale Price'   : "{:.2f} xtz".format(min_sale) if min_sale != float('inf') else ''            
        }
    }

    return token_data

# Compute the respective lowest price of all tokens
def token_lowest_price(tokens):
    for i , token in enumerate(tokens):
        r = requests.request("GET", f"https://akaswap.com/api/v2/fa2tokens/{token['contract']}/{token['tokenId']}/records")
        record_list = json.loads(r.text)['records']
        min_sale = float('inf')
        for record in reversed(record_list):
            if record['type'] in ['collect_offer','collect']:
                min_sale = record['price'] if record['price'] < min_sale else min_sale
        tokens[i]['lowestSoldPrice'] = min_sale if min_sale != float('inf') else None
    return tokens

# Compute the respective average price of all tokens
def token_average_price(tokens):
    for i , token in enumerate(tokens):
        r = requests.request("GET", f"https://akaswap.com/api/v2/fa2tokens/{token['contract']}/{token['tokenId']}/records")
        record_list = json.loads(r.text)['records']
        prices = []
        for record in reversed(record_list):
            if record['type'] in ['collect_offer','collect']:
                prices.append(record['price'])
        tokens[i]['averageSoldPrice'] = statistics.mean(prices) if prices else None
    return tokens

# Compute the minimum sale price of all tokens
def token_min_sale(tokens):
    for i , token in enumerate(tokens):
        min_sale = float('inf')
        sales = token['sale']['swaps']
        for sale in sales:
            sale_xtz = sale['xtzPerToken']
            min_sale = sale_xtz if sale_xtz < min_sale else min_sale
        tokens[i]['minSalePrice'] = min_sale if min_sale != float('inf') else None
    return tokens

# Find the collectible price of all tokens
def token_collectible_price(tokens,addr):

    token_dict = dict()
    for token in tokens:
        token_dict[token['contract'] + str(token['tokenId'])] = 0 
    
    r = requests.request("GET", f"https://api.akaswap.com/v2/accounts/{addr}/records")
    records = json.loads(r.text)['records']
    for record in records:
        if record.get('contract') and token_dict.get(record['contract'] + str(record['tokenId'])) != None:
            if record["type"][:7] == 'collect':
                token_dict[record['contract'] + str(record['tokenId'])] += (record['amount'] * record['price'])
            elif record["type"][:4] == 'sell':
                token_dict[record['contract'] + str(record['tokenId'])] -= (record['amount'] * record['price'])

    for i , token in enumerate(tokens):
        tokens[i]['collectiblePrice'] = round(token_dict[token['contract'] + str(token['tokenId'])] / token['owners'][addr],2)

    return tokens

# Find own amounts of all tokens
def token_own_amount(tokens,addr):
    for i in range(len(tokens)):
        tokens[i]['ownAmount'] = tokens[i]['owners'][addr]
    return tokens    

# Given option to sort token
def token_sort(tokens,option,rev,addr):

    titles = {
        # Creation
        "highestSoldPrice"  : "Highest Transaction Price",
        "recentlySoldPrice" : "Recent Transaction Price",
        "lowestSoldPrice"   : "Lowest Transaction Price",
        "averageSoldPrice"  : "Average Transaction Price",
        "minSalePrice"      : "Current Minimum Sale Price",
        "amount"            : "Amount",
        # Collection
        "collectiblePrice"  : "Collectible Price",
        "ownAmount"         : "Own Amount",
        # All
        "tokenId"           : "Token ID",
        "name"              : "Name"
    }

    # Creation
    if option == "lowestSoldPrice":
        tokens = token_lowest_price(tokens)
    elif option == "averageSoldPrice":
        tokens = token_average_price(tokens)
    elif option == "minSalePrice":
        tokens = token_min_sale(tokens)
    # Collection
    elif option == "collectiblePrice":
        tokens = token_collectible_price(tokens,addr)
    elif option == "ownAmount":
        tokens = token_own_amount(tokens,addr)

    
    tokens = sorted(tokens,reverse=(True if rev == 'reverse_True' else False), key=lambda token: token[option] if token[option] else ('' if option == 'name' else 0))
    
    ranking_data = list()
    for i , token in enumerate(tokens):
        if option == "name" or option == "tokenId":
            token_option = None
        elif option == "amount" or option == "ownAmount":
            token_option = token[option] 
        else:
            token_option = "{:.2f} xtz".format(token[option] / 1000000) if token[option] != None else ''
        token_dict = {
            'rank'     : i+1,
            'color'    : 'rgba(255, 255, 255, 1)' if (i+1) % 2 else 'rgba(236, 236, 236, 0.8)',
            'tokenId'  : token['tokenId'],
            'name'     : token['name'],
            'platform' : platforms[token['contract']][0],
            'url'      : f"https://akaswap.com/{platforms[token['contract']][1]}/{token['tokenId']}",
            'photo'    : token['displayUri'].replace("ipfs://", "https://ipfs.io/ipfs/") if token['displayUri'] != None else None,
            'option'   : token_option
        }

        ranking_data.append(token_dict)

    return ranking_data , titles[option]

# Give user to find tokens
def find_token_list(addr,user,platform):

    target = 'creation' if user =='creator' else 'collection'
    tokens = []
    for pf in platform:
        offset = 0
        while True:
            r = requests.request("GET", f"https://akaswap.com/api/v2/accounts/{addr}/{target}s?limit=30&offset={offset}&contracts={contracts[pf]}")

            if r.status_code == 404:
                raise Error(f'Non-existent {user.capitalize()}')

            count = json.loads(r.text)['count']

            if not count:
                break

            tokens += json.loads(r.text)['tokens']
            offset += 30

            if offset >= count:
                break
            
    if not len(tokens):
        raise Error(f'Non-existent {target.capitalize()}')

    return tokens , find_alias(addr)

# Rank data winthhin user
def rank_within_user(request,user):
    ranking_data = None
    if request.method == 'POST':
        addr = request.form[f'{user}_addr']
        if not addr:
            flash(f'No {user}', 'danger')
        else:
            try:
                option = request.form['option']
            except:
                flash('No Ranking Attribute', 'danger')
                return None
            try:
                reverse = request.form['reverse']
            except:
                flash('No Reverse Option', 'danger')
                return None
            try:
                platform = request.form.getlist('platform')
            except:
                flash('No Platform', 'danger')
                return None
            try:
                tokens , name = find_token_list(addr,user,platform)
            except Exception as e:
                flash(e.msg, 'danger')
                return None
            
            tokens, title = token_sort(tokens,option,reverse,addr)

            ranking_data = {
                user.capitalize() : name,
                'URL'             : f'https://akaswap.com/tz/{addr}',
                'Current Time'    : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'tokens'          : tokens,
                'option'          : title,
                'Unit'            : 'Amount' if option == 'amount' or option == "ownAmount" else 'Price'
            }

    return ranking_data

# Compute rate 
def compute_rate(tokens,type):
    for i , token in enumerate(tokens):
        tokens[i][f'{type}Rate'] = round(token[f'{type}Amount'] / token[f'{type}Total'],2)
    return tokens    

# Compute item amount
def bundle_Item_amount(tokens):
    for i , token in enumerate(tokens):
        tokens[i]['bundleItemAmount'] = 0
        for item in token['bundleItems']:
            tokens[i]['bundleItemAmount'] += item['amount']
    return tokens    

# Transform time
def transform_time(tokens,time_type):
    for i , token in enumerate(tokens):
        tokens[i][time_type] = datetime.strptime(token[time_type], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
    return tokens    

# Find all tokens of a specific type
def find_type_list(type,filter):

    tokens, offset = [], 0
    limit = 30 if type == 'auction' else 20

    while True:
        r = requests.request("GET", f"https://api.akaswap.com/v2/{type}s?limit={limit}&offset={offset}")

        count = json.loads(r.text)['count']

        if not count:
            break

        tokens += json.loads(r.text)[f'{type}s']
        offset += limit

        if offset >= count:
            break
            
    if not len(tokens):
        raise Error(f'Non-existent {type.capitalize()}')

    if filter == 'filter_True':
        for token in list(tokens):
            if datetime.strptime(token['cancelTime'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8) < datetime.now():
                tokens.remove(token)

    return tokens

# Given option to sort token within a specific type
def type_sort(tokens,option,rev,type):

    info = {
        # Gacha
        "gachaAmount"       : {'title' : "Amount"              , 'unit': "Amount"},
        "gachaTotal"        : {'title' : "Total"               , 'unit': "Amount"},
        "gachaRate"         : {'title' : "Rate"                , 'unit': "Rate"},
        "xtzPerGacha"       : {'title' : "Price"               , 'unit': "Price"},
        "gachaItemAmount"   : {'title' : "Item Amount"         , 'unit': "Amount"},
        "cancelTime"        : {'title' : "Cancel Time"         , 'unit': "Time"},
        "gachaId"           : {'title' : "Gacha ID"            , 'unit': ""},
        # Auction
        "auctionAmount"     : {'title' : "Amount"              , 'unit': "Amount"},
        "startPrice"        : {'title' : "Start Price"         , 'unit': "Price"},
        "directPrice"       : {'title' : "Direct Price"        , 'unit': "Price"},
        "currentBidPrice"   : {'title' : "Current Bid Price"   , 'unit': "Price"},
        "currentStorePrice" : {'title' : "Current Store Price" , 'unit': "Price"},
        "raisePercentage"   : {'title' : "Raise Percentage"    , 'unit': "Rate"},
        "dueTime"           : {'title' : "Due Time"            , 'unit': "Time"},
        "auctionId"         : {'title' : "Auction ID"          , 'unit': ""},
        # Bundle
        "bundleAmount"      : {'title' : "Amount"              , 'unit': "Amount"},
        "bundleTotal"       : {'title' : "Total"               , 'unit': "Amount"},
        "bundleRate"        : {'title' : "Rate"                , 'unit': "Rate"},
        "xtzPerBundle"      : {'title' : "Price"               , 'unit': "Price"},
        "bundleItemAmount"  : {'title' : "Item Amount"         , 'unit': "Amount"},
        "bundleId"          : {'title' : "Bundle ID"           , 'unit': ""},
        # All
        "issueTime"         : {'title' : "Issue Time"          , 'unit': "Time"},
        "title"             : {'title' : "Title"               , 'unit': ""} 
    }

    # Bundle
    if option[-4:] == "Rate":
        tokens = compute_rate(tokens,type)
    elif option == "bundleItemAmount":
        tokens = bundle_Item_amount(tokens)
    elif option[-4:] == "Time":
        tokens = transform_time(tokens,option)

    tokens = sorted(tokens,reverse=(True if rev == 'reverse_True' else False), key=lambda token: token[option] if token[option] else ('' if option == 'Title' else 0))
    
    ranking_data = list()
    for i , token in enumerate(tokens):
        if info[option]['unit'] == "":
            token_option = None
        elif info[option]['unit'] == "Price":
            token_option = "{:.2f} xtz".format(token[option] / 1000000) if token[option] != None else ''
        elif info[option]['unit'] == "Time":
            token_option = token[option].strftime("%Y-%m-%d %H:%M:%S")
        else:
            token_option = token[option] 

        if token["contract"] == 'KT1NL8H5GTAWrVNbQUxxDzagRAURsdeV3Asz':
            version = 'v1/' 
        elif token["contract"] == 'KT1GsdckBVCsgqp6ERYLnyawyXACAAQspPv6':
            version = 'v2/'
        else:
            version = ''

        object_item = token if type == "auction" else token[f"{type}Items"][0]

        token_dict = {
            'rank'   : i+1,
            'color'  : 'rgba(255, 255, 255, 1)' if (i+1) % 2 else 'rgba(236, 236, 236, 0.8)',
            'Id'     : token[f'{type}Id'],
            'name'   : token['title'],
            'url'    : f"https://akaswap.com/{type}/{version}{token[f'{type}Id']}",
            'photo'  : object_item['token'].get('displayUri').replace("ipfs://", "https://ipfs.io/ipfs/") if object_item['token']['displayUri'] != None else None,
            'option' : token_option
        }

        ranking_data.append(token_dict)

    return ranking_data , info[option]['title'], info[option]['unit']

# Rank all data of a sepcific type
def rank_within_type(request,type):
    ranking_data = None
    filter = False
    if request.method == 'POST':
        try:
            option = request.form['option']
        except:
            flash('No Ranking Attribute', 'danger')
            return None
        if type == 'gacha':
            try:
                filter = request.form['filter']
            except:
                flash('No Filter Option', 'danger')
                return None
        try:
            reverse = request.form['reverse']
        except:
            flash('No Reverse Option', 'danger')
            return None
        try:
            tokens = find_type_list(type,filter)
        except Exception as e:
            flash(e.msg, 'danger')
            return None
            
        tokens, title, unit = type_sort(tokens,option,reverse,type)

        ranking_data = {
            'Current Time'    : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'tokens'          : tokens,
            'option'          : title,
            'Unit'            : unit
        }

    return ranking_data

# Filter thansaction record
def transaction_record(user_addr,platform,type,action,start_time,end_time):

    start_time = (datetime.strptime(start_time,"%Y-%m-%d") - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time = (datetime.strptime(end_time,"%Y-%m-%d") - timedelta(hours=8) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    actions = []
    for t in type:
        actions += types[t]

    for a in list(actions):
        if a.split('_')[0] not in action and not(a == 'cancel_swap' and 'swap' in action):
            actions.remove(a)

    record_data = []

    r = requests.request("GET", f"https://api.akaswap.com/v2/accounts/{user_addr}/records?startTime={start_time}&endTime={end_time}")
    records = json.loads(r.text)['records']
    for record in records:
        if (len(platform) == 5 or (record.get("contract") and platforms[record['contract']][1] in platform)) and record["type"] in actions: 
            new_record = {
                'color'     : 'rgba(236, 236, 236, 0.8)' if len(record_data) % 2 else 'rgba(255, 255, 255, 1)',
                'time'      : datetime.strptime(record['timestamp'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8),
                'platform'  : platforms[record["contract"]][0] if record.get("contract") else '',
                'from'      : record["fromAlias"] if record.get("fromAlias") else (f'{record["from"][:3]}...{record["from"][-3:]}' if record["from"] else ''),
                'from_url'  : f'https://akaswap.com/tz/{record["from"]}' if record["from"] else 'https://akaswap.com/',
                'to'        : record["toAlias"] if record.get("toAlias") else (f'{record["to"][:3]}...{record["to"][-3:]}' if record["to"] else ''),
                'to_url'    : f'https://akaswap.com/tz/{record["to"]}' if record["to"] else 'https://akaswap.com/',
                'token'     : record["tokenName"],
                'token_url' : f"https://akaswap.com/{platforms[record['contract']][1]}/{record['tokenId']}" if record.get("contract") else 'https://akaswap.com/',
                'auction'   : record["type"].replace('_',' '),
                'amount'    : record["amount"],
                'price'     : "{:.2f} xtz".format(record["price"] / 1000000) if record["price"] != None else ''
            }
            record_data.append(new_record)
        continue

    return record_data

app = Flask(__name__)

@app.route("/ranking/creation", methods=['GET', 'POST'])
def ranking_creation():
    return render_template("ranking_creation.html",data=rank_within_user(request,'creator'))

@app.route("/ranking/collection", methods=['GET', 'POST'])
def ranking_collection():
    return render_template("ranking_collection.html",data=rank_within_user(request,'collector'))

@app.route("/ranking/gacha", methods=['GET', 'POST'])
def ranking_gacha():
    return render_template("ranking_gacha.html",data=rank_within_type(request,'gacha'))

@app.route("/ranking/auction", methods=['GET', 'POST'])
def ranking_auction():
    return render_template("ranking_auction.html",data=rank_within_type(request,'auction'))

@app.route("/ranking/bundle", methods=['GET', 'POST'])
def ranking_bundle():
    return render_template("ranking_bundle.html",data=rank_within_type(request,'bundle'))


@app.route("/ranking", methods=['GET'])
def ranking():
    return render_template("ranking.html")

@app.route("/history", methods=['GET', 'POST'])
def history():
    token_data = None
    if request.method == 'POST':
        token_id = request.form['token_id']
        if not token_id:
            flash('No Token', 'danger')
        else:
            try:
                platform = request.form['platform']
            except:
                flash('No Platform', 'danger')
                return render_template("history.html",data=token_data)
            try:
                token_id = int(token_id)
            except:
                flash('Invalid Token ID', 'danger')
                return render_template("history.html",data=token_data)
            token_data = token_price_history(token_id,platform)
    return render_template("history.html",data=token_data)

@app.route("/record", methods=['GET', 'POST'])
def record():
    record_data = {
        'Default Start Time' : (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        'Default End Time' : datetime.now().strftime("%Y-%m-%d")
    }
    if request.method == 'POST':
        user_addr, start_time, end_time = request.form['user_addr'], request.form['start_time'], request.form['end_time']
        if not user_addr:
            flash('No User', 'danger')
        elif not start_time:
            flash('No Start Time', 'danger')
        elif not end_time:
            flash('No End Time', 'danger')
        else:
            try:
                platform = request.form.getlist('platform')
            except:
                flash('No Platform', 'danger')
                return render_template("record.html",data=record_data)
            try:
                type = request.form.getlist('type')
            except:
                flash('No Type', 'danger')
                return render_template("record.html",data=record_data)
            try:
                action = request.form.getlist('action')
            except:
                flash('No Action', 'danger')
                return render_template("record.html",data=record_data)
            records = transaction_record(user_addr,platform,type,action,start_time,end_time)
            if not records:
                flash('No Record', 'danger')
            else:
                record_data = {
                    'User'         : find_alias(user_addr),
                    'URL'          : f'https://akaswap.com/tz/{user_addr}',
                    'Current Time' : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'Start Time'   : start_time,
                    'End Time'     : end_time,
                    'Records'      : records
                }
    return render_template("record.html",data=record_data)

@app.route("/")
def home():
    return render_template("home.html")

if __name__ == '__main__':
    app.debug = True
    app.secret_key = os.urandom(64)
    app.run()