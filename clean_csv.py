import ast
import pandas as pd
import json

base_university = 'UC San Diego'

dp2dp_name = {
    'jacob': 'Engineering',
    'biology': 'Biology',
    'economics': 'Economics',
    'hdsi': 'Halicioglu Data Science Institute',
    'math': 'Mathematics',
    'psychology': 'Psychology',
    'sociology': 'Sociology',
    'psychiatry': 'Psychiatry',
    'physics': 'Physics',
    'politics': 'Politics',
    'tilos': 'TILOS',
    'medicine': 'Medicine',
    'global': 'Global Policy and Strategy',
    'rady': 'Rady School of Management',
    'chemistry': 'Chemistry and Biochemistry',
}



if __name__ == '__main__':
    df = pd.read_csv('/Users/charon/学习/crawler_system/data/ucsd/jacob/faculty_profiles.csv')
    df = df.drop(columns=['grad_students'])
    #
    # for col in df.columns:
    #     if col in ['grad students', 'postdocs', 'keyword']:
    #         df[col] = df[col].apply(lambda x: ast.literal_eval(x))
    #         df[col] = df[col].apply(lambda x: x if x != {} else )
    #     else:
    #         df[col] = df[col].apply(lambda x: x if x != "{}" else {})
    # df_json = df.to_json(orient="records")
    # with open('/Users/charon/学习/crawler_system/data/ucsd/jacob/cleaned_faculty_profiles.json', 'w') as f:
    #     f.write(df_json)
    #     # json.dump(df_json, f, indent=4)
    # with open('/Users/charon/学习/crawler_system/data/ucsd/jacob/cleaned_faculty_profiles.json', 'r') as f:
    #     data = json.load(f)
    #
    # # simulate the reading
    # for i in range(5):
    #     print(i, {name: type(data[i][name]) for name in data[i]})
    import re

    with open('/Users/charon/学习/crawler_system/logs/20240726_142406_jacob_keyword_retrieval.log', 'r') as f:
        lines = f.readlines()



    for line in lines:
        if 'Representative keywords for' in line:
            name_match = re.search(r"Representative keywords for (.*?) found in lab website:", line)
            dict_match = re.search(r"Representative keywords for .*? found in lab website: ({.*})", line)
            if name_match:
                name = name_match.group(1)
                # print(f"Name: {name}")
                if dict_match:
                    dict_str = dict_match.group(1)
                    df.loc[df['name']==name, 'keyword'] = dict_str
    print(df['keyword'].head())
    df.to_csv('/Users/charon/学习/crawler_system/data/ucsd/jacob/faculty_profiles.csv', index=False)
