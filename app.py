import warnings

import pandas as pd
import torch
from flask import Flask
from flask import request
from sklearn.preprocessing import normalize

from models.data_process import load_adult_income_dataset, encoder_process
from models.run_MLP import load_model, test_model
from utils.helper import *
from utils.parser import parse_args

args = parse_args()
warnings.filterwarnings("ignore")  # 忽略UserWarning兼容性警告

np.random.seed(12345)

# ------- Initialize file ------- #
data_file = args.data_path + 'final_data.csv'
pre_file = args.out_dir + getFileName('prediction', 'csv')
dice_file = args.out_dir + getFileName('dice', 'csv')
train_data = json.loads(pd.read_csv(args.data_path + 'train.csv', header=0).to_json(orient='records'))
pre_data = json.loads(pd.read_csv(pre_file, header=0).to_json(orient='records'))
pre_data_len = len(pre_data)
diceData = pd.read_csv(dice_file, header=0)
with open(args.out_dir + getFileName('influence', 'json'), 'r', encoding='utf-8') as fp:
    influenceData = json.load(fp)
    print('=====influence file read done')
fp.close()
with open(args.out_dir + getFileName('ianchors_beam', 'json'), 'r', encoding='utf-8') as fp:
    anchorData = json.load(fp)
    print('=====anchor file read done')
fp.close()
# with open(args.out_dir + getFileName('dice', 'json'), 'r', encoding='utf-8') as fp:
#     diceData = json.load(fp)
#     print('=====dice file read done')
# fp.close()

# ------- Initialize Model ------- #
dataset, target, encoder, categorical_names = load_adult_income_dataset()
model = load_model()
loss, acc, FN, TN, FP, TP = test_model()


# ------ Help Function ------- #
# 获取训练集中的sample
def getSampleCovered(covered):
    def getAnchorSample(sam):
        for feature in range(3, dataset.shape[1]):
            sam[feature] = categorical_names[feature][sam[feature]]
        df = pd.DataFrame(sam, columns=adult_process_names)
        return df.to_json()

    new_ct = []
    for ct_item in covered:
        df = pd.DataFrame(ct_item, columns=adult_process_names)
        for feature in discrete_features:
            df[feature] = df[feature].map(lambda k: categorical_names[feature][k])
        new_ct.append(df.to_dict(orient='record'))
    return np.array(new_ct)


# ------ Initialize WebApp ------- #
app = Flask(__name__)


@app.route('/getPredData')
def getPredData():
    idx = -1
    idx = request.args.get('idx')

    response = {'total': len(pre_data)}

    if idx is not None:
        idx = int(idx)
        response['data'] = pre_data[idx]
    else:
        response['data'] = pre_data

    return toJson(response)


@app.route('/getInstance')
def getInstance():
    idx = -10
    try:
        idx = int(request.args.get('params'))
        if idx < 0 or idx > pre_data_len:
            return f"Please enter a sample number in the range (1, ${pre_data_len})."
    except:
        return f"Please enter a sample number in the range (1, ${pre_data_len})."

    sample = pre_data[idx]
    response = {'id': idx, 'total': pre_data_len, 'sample': sample}
    return toJson(response)


@app.route('/getTrainSample')
def getTrainSample():
    idx = -10
    train_data_len = len(train_data)
    try:
        idx = int(request.args.get('params'))
        if idx < 0 or idx > train_data_len:
            return f"Please enter a sample number in the range (1, ${train_data_len})."
    except:
        return f"Please enter a sample number in the range (1, ${train_data_len})."

    sample = train_data[idx]
    response = {'id': idx, 'sample': sample}
    return toJson(response)


@app.route('/getAnchor')
def getAnchor():
    try:
        idx = request.args.get('params')
    except:
        return f"Please enter a sample number ."

    anchor = anchorData[idx]

    response = {}
    response['feature'] = anchor['feature']
    response['precision'] = anchor['precision']
    response['coverage'] = anchor['coverage']
    response['covered_false'] = getSampleCovered(anchor['covered_false'])
    response['covered_true'] = getSampleCovered(anchor['covered_true'])
    return toJson(response)


# 获取相似数据-影响训练点
@app.route('/getInfluenceData')
def getInfluenceData():
    try:
        idx = request.args.get('params')
    except:
        return f"Please enter a sample number."
    total = influenceData['total']
    inData = influenceData[str(idx)]
    time = inData['time_calc_influence_s']
    influence = inData['influence']
    harmful = inData['harmful']
    helpful = inData['helpful']

    response = {'total': total, 'time': time, 'influence': [], 'harmful': [], 'helpful': [], 'max': inData['max'],
                'min': inData['min']}
    for i in range(len(harmful)):
        response['harmful'].append({
            'id': harmful[i],
            'value': influence[harmful[i]],
        })
        response['helpful'].append({
            'id': helpful[i],
            'value': influence[helpful[i]],
        })
    for i in range(len(influence)):
        response['influence'].append({
            'id': i,
            'value': influence[i],
            'sign': (1 if influence[i] else 0)
        })

    return toJson(response)


@app.route('/getDiceData')
def getDiceData():
    try:
        idx = int(request.args.get('params'))
    except:
        return f"Please enter a sample number."

    # inData = diceData[str(idx)]
    # cfs_list = inData['cfs_list']
    # pf = pd.DataFrame(cfs_list, columns=adult_process_names)
    # cfs_list = pf.to_dict(orient='records')
    # response = {'cfs_list': cfs_list}
    # return toJson(response)

    ans = []
    sample = pre_data[idx]
    list = diceData[diceData['from'] == idx]
    list['percentage'] = list['income']
    list = list.to_dict(orient='records')
    ans.append(sample)
    ans.extend(list)
    return toJson(ans)


@app.route('/getModeForm')
def getModeForm():
    return toJson(categorical_names)


@app.route('/getModelInfo')
def getModelInfo():
    ans = {'loss': loss, 'acc': acc, 'FN': FN, 'TN': TN, 'FP': FP, 'TP': TP, 'categorical_names': categorical_names}
    return toJson(ans)


@app.route('/runModel', methods=['GET', 'POST'])
def runModel():
    params = request.json
    val = [[float(params[i]) for i in params]]
    val = np.array(val)
    val = encoder_process(val, encoder)
    testVal = normalize(val)
    testVal = torch.FloatTensor(testVal)

    x = testVal[0].to(args.device)
    out = model(x)
    _, pred = torch.max(out, 0)
    prediction = pred.item()
    percentage = round(out[1].item(), 5)

    ans = {'prediction': prediction, 'percentage': percentage}
    print(ans)
    return toJson(ans)


# ------- Run WebApp ------- #

if __name__ == '__main__':
    app.run(port=3001, host="0.0.0.0", debug=True, threaded=True)
# serve(app, host="0.0.0.0",port=3001)
