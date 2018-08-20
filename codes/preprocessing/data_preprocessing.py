#!/usr/bin/python
# -*- coding: UTF-8 -*-

import pandas as pd
import numpy as np
from datetime import datetime,timedelta
import os, sys, json, csv, re

common_disk_list = ['boot', 'rt', 'home', 'monitor', 'tmp']  #通过generate_plot_data得到所有主机公共的磁盘目录
######################################################################################
#Author: 王靖文

#日期转换
def trans_date(date_str):
    return date_str[:4] + '-' + date_str[4:6] + '-' + date_str[6:8] + ' ' + date_str[8:] + ':00:00'

def trans_alarm_date(date_str):
    return date_str[:4] + '-' + date_str[4:6] + '-' + date_str[6:11] + ':00:00'

#最开始要处理的程序，把raw_data里指标数据的log文件转成csv文件
def process_raw_data(origin_dir, output_dir):

    f_list = os.listdir(origin_dir)
    for i in f_list:  ##每个log文件
        if os.path.splitext(i)[1] == '.log':
            file_name = os.path.join(output_dir, os.path.splitext(i)[0] + '.csv')
            # if not os.path.exists(file_name):
            #     os.makedirs(file_name)
            with open(origin_dir + "/" + i, "r") as fp1:
                origin_data = fp1.read()
                origin_data_list = origin_data.split(']')[:-1]  # 每一天的数据组成的list
                data_list = []  # json dict list
                for item in origin_data_list:
                    if (len(item) > 0 and item[-1] != ']'):
                        item = item + ']'
                    hour_data_list = item[1:-1].split('}, ')[:-1]
                    # print(hour_data_list)
                    for hour_data in hour_data_list:
                        if (len(hour_data) > 0 and item[-1] != '}'):
                            hour_data = hour_data + '}'
                        data_list.append(json.loads(hour_data))  # json list
                        # print(hour_data)
                #print(data_list)
                #print(list(data_list[0].keys()))

                df = pd.DataFrame(data_list)
                #print(df.shape)
                df.to_csv(file_name,sep=',',index=False)
    print('process raw data finished!')

#只获取时间、最大值、最小值特征，一方面为了画图使用，另一方面为了后续合成特征
def generate_plot_data(origin_dir, output_dir):
    #如果output_dir没有创建，则需要先创建该文件夹
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    f_list = os.listdir(origin_dir)
    for file in f_list:
        file_path = os.path.join(origin_dir, file)
        file_name = os.path.splitext(file)[0]
        file_name_list = file_name.split('_')
        h = file_name_list.index("hourly")
        host_name_list = []
        for a in range(1, h):   #有的主机名用下划线连接
            host_name_list.append(file_name_list[a])  #主机名可能带有下划线，名字很长
        host_name = '_'.join(host_name_list)
        device_name = file_name_list[-1]  #设备名称是第-1个元素（list从末尾往前数）
        print('host_name = {0}, device_name = {1}'.format(host_name, device_name))
        if file_name.endswith("disk"):  # 磁盘文件中diskname字段有不同的磁盘名
            data = pd.read_csv(file_path, usecols=['archour','diskname', 'maxvalue','minvalue'], dtype=str)
            for diskname, group in data.groupby('diskname'):   #对diskname分组存储到不同文件中
                disk_name = 'rt' if len(diskname) == 1 and diskname[0] == '/' else diskname[1:]  #将主机的根目录用rt表示
                disk_name = disk_name.replace('/', '_')
                output_file_name = '_'.join([host_name, device_name, disk_name]) + '.csv'
                output_file = os.path.join(output_dir, output_file_name)
                group.drop(['diskname'],axis=1, inplace=True)
                group['archour'] = group['archour'].apply(trans_date)
                group.to_csv(output_file, sep=',', index=False, header=False)
        else:
            output_file_name = host_name+ '_' + device_name + '.csv'
            output_file = os.path.join(output_dir, output_file_name) #主机名 部件名
            data = pd.read_csv(file_path,usecols=['archour','maxvalue','minvalue'], dtype=str)  #时间 最大值 最小值
            data['archour'] = data['archour'].apply(trans_date)
            data.to_csv(output_file, sep=',', index=False, header=False)
    print('generate plot data finished!')

#对数据缺失的文件进行插值处理，取平均
def insert_missing_data(origin_dir, output_dir):
     f_list = os.listdir(origin_dir)
     if(not os.path.exists(output_dir)):
         os.makedirs(output_dir)
     for file in f_list:
        file_path = os.path.join(origin_dir, file)
        file_name = os.path.splitext(file)[0]
        output_file_path = os.path.join(output_dir, file_name + '.csv')

        print(file)
        df = pd.read_csv(file_path, sep=',', header=None, names=['archour', 'maxvalue', 'minvalue'], dtype=str)
        df['archour'] = df['archour'].apply(lambda x: datetime.strptime(x, '%Y-%m-%d %H:%M:%S'))
        df[['maxvalue', 'minvalue']] = df[['maxvalue', 'minvalue']].apply(np.float64)
        if df.shape[0] == 139 * 24:
            df.to_csv(output_file_path, sep=',', index=False, header=False, float_format='%.1f')
            continue
        #所有文件的末尾都是22点或23点
        df['day'] = df['archour'].apply(lambda x: datetime(x.year, x.month, x.day))
        df_out = pd.DataFrame(columns=df.columns)
        last_day = datetime(2018, 6, 11)
        group = df.groupby(df['day'])
        is_exception = False
        print_is_exception = False
        except_day = datetime(1, 1, 1)
        except_day_data_list = []
        for day, day_df in group:
            if(is_exception):
                print_is_exception = True
                for i in range(1, day.day - except_day.day):  #因为后边还会插入day（当前天）的数据
                    tmp_df = pd.DataFrame(except_day_data_list)
                    tmp_df['archour'] = tmp_df['archour'].apply(lambda x: x + timedelta(days=i))
                    tmp_df['day'] = tmp_df['day'].apply(lambda x: x + timedelta(days=i))
                    df_out = df_out.append(tmp_df)
                is_exception = False
                except_day = datetime(1, 1, 1)
                except_day_data_list = []

            day_data_list = day_df.to_dict('record')
            day_df = day_df.reset_index(drop=True)
            last_row = day_df.loc[day_df.shape[0] - 1]
            if last_row['archour'].hour == 22: #缺23点的数据
                if last_row['day'] < last_day: #不是最后一天的数据
                    front_time_data = day_df.loc[day_df.shape[0] - 1]
                    try:
                        nxt_day_df = group.get_group(day + timedelta(days=1)).reset_index(drop=True)
                    except:
                        nxt_day_df = day_df
                        is_exception = True
                        except_day = day
                    nxt_time_data = nxt_day_df.loc[0]
                    now_time = front_time_data['archour'] + timedelta(hours=1)
                    now_max_value = (front_time_data['maxvalue'] + nxt_time_data['maxvalue']) / 2
                    now_min_value = (front_time_data['minvalue'] + nxt_time_data['minvalue']) / 2
                else: #最后一天的数据
                    front_time_data = day_df.loc[day_df.shape[0] - 1]
                    pre_front_time_data = day_df.loc[day_df.shape[0] - 2]
                    now_time = front_time_data['archour'] + timedelta(hours=1)
                    now_max_value = (front_time_data['maxvalue'] + pre_front_time_data['maxvalue']) / 2
                    now_min_value = (front_time_data['minvalue'] + pre_front_time_data['minvalue']) / 2
                hour_data_dict = {'archour': now_time, 'day': datetime(now_time.year, now_time.month, now_time.day) , 'maxvalue': now_max_value, 'minvalue': now_min_value}
                day_data_list.append(hour_data_dict)

            if(len(day_data_list) == 24):
                try:
                    group.get_group(day + timedelta(days=1)).reset_index(drop=True)
                except:
                    is_exception = True
                    except_day = day
                if (is_exception):  # 相邻两天之间间隔了好几天，比如ywn_monitor1主机在2018年2月4日的数据下一天是2月8日
                    except_day_data_list = day_data_list.copy()
                df_out = df_out.append(pd.DataFrame(day_data_list))
                continue

            day_data_res = [day_data_list[0]]
            for i in range(1, len(day_data_list)):
                now_time = day_data_list[i]['archour']
                front_time = day_data_list[i - 1]['archour']
                if(now_time.hour - front_time.hour == 1):
                    day_data_res.append(day_data_list[i])
                else:
                    for hour_idx in range(1, now_time.hour - front_time.hour):
                        missing_time = front_time + timedelta(hours=hour_idx)
                        missing_max_value = (day_data_list[i - 1]['maxvalue'] + day_data_list[i]['maxvalue']) / 2
                        missing_min_value = (day_data_list[i - 1]['maxvalue'] + day_data_list[i]['maxvalue']) / 2
                        hour_data_dict = {'archour': missing_time, 'day': datetime(missing_time.year, missing_time.month, missing_time.day), 'maxvalue': missing_max_value, 'minvalue': missing_min_value}
                        day_data_res.append(hour_data_dict)
                    # 这里要记着也插入当前时刻的数据
                    day_data_res.append(day_data_list[i])
            if(day_data_res[-1]['archour'].hour != 23):  #还有一天最后的时刻是19点或者20点
                now_time = day_data_res[-1]['archour']
                for hour_idx in range(1, 24 - now_time.hour):
                    missing_time = now_time + timedelta(hours=hour_idx)
                    missing_max_value = (day_data_res[-1]['maxvalue'] + day_data_list[-2]['maxvalue']) / 2
                    missing_min_value = (day_data_res[-1]['maxvalue'] + day_data_list[-2]['maxvalue']) / 2
                    hour_data_dict = {'archour': missing_time,'day': datetime(missing_time.year, missing_time.month, missing_time.day), 'maxvalue': missing_max_value, 'minvalue': missing_min_value}
                    day_data_res.append(hour_data_dict)
            #print('data_res= ', len(day_data_res))
            if(is_exception):  #相邻两天之间间隔了好几天，比如ywn_monitor1主机在2018年2月4日的数据下一天是2月8日
                except_day_data_list = day_data_res.copy()
            df_out = df_out.append(pd.DataFrame(day_data_res))
        df_out.drop(['day'], axis=1, inplace=True)
        df_out.to_csv(output_file_path, sep=',', index=False, header=False, float_format='%.1f')


#检查所有文件是否数据完整  使用shape[0]是否能对24整除判断
def check_completeness(origin_dir):
    f_list = os.listdir(origin_dir)
    for file_name in f_list:
        with open(origin_dir + "/" + file_name, "r") as fp1:  # 通过时间字段 对hostname的不同部件的max min值merge到同一个dataframe中
            data = pd.read_csv(fp1, sep=',', dtype=str, header=None, index_col=None)  # header=None设置列名为空，自动用0开头的数字替代
            row_num = data.shape[0]
            if row_num % 24 != 0:
                print (file_name)
                print(row_num)

def generate_alarm_data(alarm_processed_file,node_alias_file,alarm_out_file):
    df_node_alias = pd.read_csv(node_alias_file, sep=',', dtype=str)
    node_dict = dict(zip(df_node_alias['id'], df_node_alias['node_alias']))
    data = pd.read_csv(alarm_processed_file, sep=',', dtype=str, usecols=['node_alias','last_time','alarm_level'])  #提取告警事件文件内的主机、时间、事件级别
    data['node_alias'] = data['node_alias'].apply(find_node_alias_value,node_dict = node_dict)  #node数字转成对应主机名称
    data['last_time'] = data['last_time'].apply(trans_alarm_date)   #修改日期格式
    data['alarm_level'] = '1'    #将事件级别全部赋值为1
    data.columns = ['hostname', 'archour','event']
    print (data)
    data.to_csv(alarm_out_file, sep=',', index=False)

def find_node_alias_value(node_key,node_dict): #在node_dict中 找到id对应node_alias 也就是主机名
    node_value = node_dict[node_key]
    return node_value.lower()        #全部转换为小写

#获得matlab需要画图用的数据
def generate_subplot_data(predict_data, subplot_data_dir):
    if not os.path.exists(subplot_data_dir):
        os.makedirs(subplot_data_dir)
    data = pd.read_csv(predict_data, sep=',',dtype=str)
    for hostname,group in data.groupby('hostname'):
        subplot_data_file = os.path.join(subplot_data_dir,hostname+'.csv')
        group.drop(['hostname'], axis=1, inplace=True)
        group.to_csv(subplot_data_file, sep=',', index=False, header=False)


######################################################################################
#Author: 普俊韬

#START 'cffex-host-alarm.csv' process code
def process_alarm_data(host_alarm_dir, output_dir):

    #Last update: 20180627
    #定义原始数据路径
    host_alarm_rawdata_dir = os.path.join(host_alarm_dir,"cffex-host-alarm.csv")
    #定义告警事件数据路径
    host_alarm_content_dir = os.path.join(host_alarm_dir,"cffex-host-alarm-content.csv")
    #定义告警数据处理后输出路径
    #处理后的告警数据总表
    host_alarm_processed_dir = os.path.join(output_dir,"cffex-host-alarm-processed.csv")
    #处理后的告警组件数据
    host_alarm_component_dir = os.path.join(output_dir,"cffex-host-alarm-component.csv")
    #处理后的告警类别数据
    host_alarm_category_dir = os.path.join(output_dir,"cffex-host-alarm-category.csv")
    #处理后的组件别名数据
    host_alarm_node_alias_dir = os.path.join(output_dir,"cffex-host-alarm-node-alias.csv")

    #TODO：进行原始数据的分割处理
    #读取原始数据（GBK编码，数据不带列标题）
    data = pd.read_csv(host_alarm_rawdata_dir, header = None, names=['alarm_str'], encoding = 'GBK')
    #分割数据字段，分隔符'|||'（'[|]+'),分割后扩展列
    data_processed = data['alarm_str'].str.split('[|]+',expand = True)
    #插入列标题
    data_processed.columns = ['node_name', 'node_alias', 'component', 'category', 'alarm_count', 'first_time', 'last_time', 'alarm_level', 'alarm_content']
    # 先都变成小写字母，防止大写字母主机和小写字母主机不同
    data_processed['node_alias'] = data_processed['node_alias'].apply(str.lower)
    data_processed.to_csv(os.path.join(host_alarm_dir,"cffex-host-alarm-processed.csv"), sep=',', index=False)
    #TODO：进行'component'字段的处理

    #将'component'字段提取出来作为一个DataFrame
    data_component = data_processed[['component']].copy()
    #去掉重复数据
    data_component_processed = data_component.drop_duplicates()
    #插入id列，编号从1开始
    data_component_processed['id'] = range(1,len(data_component_processed) + 1)
    #将列顺序调整为['id', 'component']
    data_component_processed = data_component_processed[['id','component']]
    #将处理后结果写入'cffex-host-alarm-component.csv'（不带行标签，utf-8编码）
    data_component_processed.to_csv(host_alarm_component_dir, sep=',', index=False, encoding='utf-8')

    #TODO：进行'category'字段的处理
    #将'category'字段提取出来作为一个DataFrame
    data_category = data_processed[['category']].copy()
    #去掉重复数据
    data_category_processed = data_category.drop_duplicates()
    #插入id列，编号从1开始
    data_category_processed['id'] = range(1,len(data_category_processed) + 1)
    #将列顺序调整为['id', 'category']
    data_category_processed = data_category_processed[['id','category']]
    #将处理后结果写入'cffex-host-alarm-category.csv'（不带行标签，utf-8）
    data_category_processed.to_csv(host_alarm_category_dir, index = 0, encoding = 'utf-8')

    #TODO：进行'node_alias'字段的处理
    #将'node_alias'字段提取出来作为一个DataFrame
    data_node_alias = data_processed[['node_alias']].copy()
    #去掉重复数据
    data_node_alias_processed = data_node_alias.drop_duplicates()
    print('node alias list shape: ', data_node_alias_processed.shape[0])
    #插入id列，编号从1开始
    data_node_alias_processed['id'] = range(1,len(data_node_alias_processed) + 1)
    #将列顺序调整为['id', 'node_alias']
    data_node_alias_processed = data_node_alias_processed[['id','node_alias']]
    #将处理后结果写入'cffex-host-alarm-node-alias.csv'（不带行标签，utf-8编码）
    data_node_alias_processed.to_csv(host_alarm_node_alias_dir, index = 0, encoding = 'utf-8')

    #TODO：将'component','category'和'node_alias'字段替换为对应的'id'值，方便后续的数据处理
    #对'component'字段进行查找和替换
    data_processed['component'] = data_processed['component'].replace(data_component_processed['component'].tolist(),data_component_processed['id'].tolist())
    #对'category'字段进行查找和替换
    data_processed['category'] = data_processed['category'].replace(data_category_processed['category'].tolist(),data_category_processed['id'].tolist())
    #对'node_alias'字段进行查找和替换
    data_processed['node_alias'] = data_processed['node_alias'].replace(data_node_alias_processed['node_alias'].tolist(),data_node_alias_processed['id'].tolist())

    #TODO: 将'alarm_content'字段替换为相应的'id'值，方便后续的数据处理
    #读入告警事件表'cffex-host-alarm-content.csv'
    data_processed_content = pd.read_csv(host_alarm_content_dir,encoding = 'GBK')
    #替换函数定义
    def re_replace(data):
        for i in range(len(data_processed_content['id'])):
            #正则表达式和字符串不存在匹配串：继续遍历
            if re.match(data_processed_content['regular_expression'][i],data) == None:
                continue
            #正则表达式和字符串存在匹配串：替换id值并返回保存
            else:
                data = str(data_processed_content['id'][i])
                return data
        return '-1'  #-1表示没有事件匹配

    #调用替换函数
    data_processed['alarm_content'] = data_processed['alarm_content'].apply(re_replace)
    #将处理后结果写入'cffex-host-alarm-processed.csv'（不带行标签，utf-8编码）
    data_processed.to_csv(host_alarm_processed_dir, index = False, encoding = 'utf-8')
    print('process alarm raw data finished!')
#END 'cffex-host-alarm.csv' process code


###jhljx
def genereate_host_event_sets(host_alarm_file_path, output_dir):
    df_alarm = pd.read_csv(host_alarm_file_path, sep=',', dtype=str, encoding='GBK')
    print('shape = ', df_alarm.shape)

    print(df_alarm.groupby(['node_alias']).size())
    for host_name_index, df_host_alarm in df_alarm.groupby(['node_alias']):
        host_name = host_name_index.lower()
        print('host name is {0}'.format(host_name))
        output_host_dir = os.path.join(output_dir, host_name)
        if not os.path.exists(output_host_dir):
            os.makedirs(output_host_dir)
        df_host_alarm['last_time'] = df_host_alarm['last_time'].apply(lambda x: datetime.strptime(trans_alarm_date(x), '%Y-%m-%d %H:%M:%S'))
        df_host_alarm = df_host_alarm.sort_values(by=['last_time'])
        output_file_path = os.path.join(output_host_dir, host_name + '_events.csv')
        df_host_alarm.to_csv(output_file_path, sep=',', index=False)

def generate_alarm_level_content(host_alarm_file_path, output_dir):
    df_alarm = pd.read_csv(host_alarm_file_path, sep=',', dtype=str, encoding='GBK')
    df_alarm = df_alarm[['alarm_level', 'alarm_content']]
    for alarm_level, df_alarm_level in df_alarm.groupby(['alarm_level']):
        df_alarm_level = df_alarm_level.drop_duplicates()
        output_file_path = os.path.join(output_dir, alarm_level + '_events.csv')
        df_alarm_level.to_csv(output_file_path, sep=',', index=False)