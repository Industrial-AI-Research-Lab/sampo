import pandas as pd
import ast
from typing import Dict

from sampo.schemas.time import Time


def fix_split_tasks(baps_schedule_df: pd.DataFrame) -> pd.DataFrame:
    """
    Process and merge information for all tasks, which were separated on the several stages during split
    :param baps_schedule_df: pd.DataFrame: schedule with info for tasks separated on stages
    :return: pd.DataFrame: schedule with merged info for all real tasks
    """
    df_len = baps_schedule_df.shape[0]
    baps_schedule_df.index = range(df_len)

    df = pd.DataFrame(columns=baps_schedule_df.columns)
    unique_ids = set([x.split('_')[0] for x in baps_schedule_df.task_id])

    for task_id in unique_ids:
        task_stages_df = baps_schedule_df.loc[baps_schedule_df.loc[:, 'task_id'].str.contains(task_id)]
        task_series = merge_split_stages(task_stages_df.reset_index(drop=True))
        df.loc[df.shape[0]] = task_series  # append

    df = df.sort_values(by=['start', 'task_name'])
    df['idx'] = range(len(df))

    return df


def merge_split_stages(task_df: pd.DataFrame) -> pd.Series:
    """
    Merge split stages of the same real task into one
    :param task_df: pd.DataFrame: one real task's stages dataframe, sorted by start time
    :return: pd.Series with the full information about the task
    """
    if len(task_df) == 1:
        df = task_df.copy()
        df['successors'] = [[tuple([x[0].split('_')[0], x[1]]) for x in df.loc[0, 'successors']]]
        return df.loc[0, :]
    else:
        df = task_df.copy()
        df = df.iloc[-1:].reset_index(drop=True)
        for column in ['task_id', 'task_name']:
            df.loc[0, column] = df.loc[0, column].split('_')[0]  # fix task id and name

        # sum up volumes through all stages
        df.loc[0, 'volume'] = sum(task_df.loc[:, 'volume'])
        df.loc[0, 'workers'] = task_df.loc[0, 'workers']

        # fix connections through all stages
        fixed_connections_lst = []
        for connections_lst in task_df.loc[:, 'successors']:
            for connection in connections_lst:
                if connection[1] != 'IFS':
                    fixed_connections_lst.append(tuple([connection[0].split('_')[0], connection[1]]))
        fixed_connections_lst = list(set(fixed_connections_lst))
        df.loc[:, 'successors'] = [fixed_connections_lst]

        # fix task's start time and duration
        df.loc[0, 'start'] = task_df.loc[0, 'start']
        df.loc[0, 'finish'] = task_df.loc[len(task_df) - 1, 'finish']
        df.loc[0, 'duration'] = (df.loc[0, 'finish'] - df.loc[0, 'start']).days + 1

        return df.loc[0, :]


def remove_service_tasks(service_schedule_df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove 'start', 'finish' and milestone tasks from the schedule
    :param service_schedule_df: pd.DataFrame: schedule (with merges stages in the case of baps) with service tasks
    :return: pd.DataFrame: schedule without information about service tasks
    """
    schedule_df = service_schedule_df.copy()

    service_df = schedule_df.loc[:, 'task_name'].str.contains('start|finish|Очередь')

    # Prepare list with service tasks ids
    service_tasks_ids = set(schedule_df.loc[service_df].loc[:, 'task_id'])

    # Remove rows with service tasks from DataFrame
    schedule_df = schedule_df.loc[~service_df]

    # Fix connections linked to the service tasks
    fixed_connections_lst = []
    for connections_lst in schedule_df.loc[:, 'successors']:
        fixed_connections_lst.append([])
        for connection in connections_lst:
            if connection[0] not in service_tasks_ids:
                fixed_connections_lst[-1].append(connection)
    schedule_df.loc[:, 'successors'] = fixed_connections_lst
    return schedule_df


def get_full_resources_dict(workers_sets: list[Dict[str, float]]) -> Dict[str, int]:
    """
    Prepare resources dict
    :param workers_sets: list with info about assigned resources for tasks
    :return: dict with resources names as keys and resources ids as values
    """
    resources_names = []
    for workers_set in workers_sets:
        resources_names.extend(list(workers_set.keys()))
    resources_names = list(set(resources_names))
    resources_ids = range(len(resources_names))
    return dict(zip(resources_names, resources_ids))


# Main function for converting schedules to validation jsons
def schedule_to_json(schedule_uploading_mode='from_df', schedule_file_path='', schedule_df=None,
                     schedule_name='schedule', deadline_date='2030-01-01') -> Dict:
    """
    Create dictionary with the JSON structure by given schedule and additional ksg info
    :param schedule_uploading_mode: one of two: 'from_df' (schedule_df needed)
    or 'from_file' (schedule_file_path needed)
    :param schedule_file_path: str path to the schedule .csv file
    :param schedule_df: pandas.Dataframe
    :param schedule_name: str
    :return: dict with JSON structure of tasks, assigned execution times and resources
    """
    if schedule_uploading_mode == 'from_file':
        df = pd.read_csv(schedule_file_path, sep=';')
    elif schedule_uploading_mode == 'from_df':
        df = schedule_df.copy()
        if not isinstance(schedule_df, pd.DataFrame):
            raise Exception("schedule_df attribute should have type pandas.DataFrame, got " +
                            str(type(schedule_df)) + " instead")
    else:
        raise Exception("unknown schedule uploading mode")

    df.loc[:, 'workers'] = [ast.literal_eval(x) for x in df.loc[:, 'workers']]
    resources_dict = get_full_resources_dict(df.loc[:, 'workers'])

    schedule_dict = {"plan_name": schedule_name, "plan_deadline": deadline_date, "activities": []}
    for i in df.index:
        if not ('start' in df.loc[i, 'task_name'] or 'finish' in df.loc[i, 'task_name']):
            activity_dict = {"activity_id": str(df.loc[i, 'task_id']),
                             "activity_name": df.loc[i, 'task_name'],
                             "start_date": str(df.loc[i, 'start']), "end_date": str(df.loc[i, 'finish']),
                             "volume": str(df.loc[i, 'volume']),
                             "measurement": str(df.loc[i, 'measurement']),
                             "labor_resources": [], "non_labor_resources": {},
                             "descendant_activities": df.loc[i, 'successors']}
            for worker in df.workers[i]:
                labor_info = {"labor_id": int(resources_dict[worker]), "labor_name": worker,
                              "volume": float(df.loc[i, 'workers'][worker]), "workers": []}
                worker_info = {"worker_id": 0, "contractor_id": 0, "contractor_name": 'Main contractor',
                               "working_periods": [{"start_datetime": str(df.loc[i, 'start']),
                                                    "end_datetime": str(df.loc[i, 'finish']),
                                                    "productivity": 1}]}
                labor_info["workers"].append(worker_info)
                activity_dict["labor_resources"].append(labor_info)
            schedule_dict["activities"].append(activity_dict)
    return schedule_dict