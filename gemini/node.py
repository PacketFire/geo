import asyncio
import json
from typing import Any
from typing import List
from typing import NamedTuple
from typing import Optional

import docker
import requests


class NodeData(NamedTuple):
    node_id: str
    password: str


def read_node_file() -> NodeData:
    try:
        with open('data/node.json', 'r') as fh:
            data = json.load(fh)
            return NodeData(data['node_id'], data['password'])
    except IOError:
        # for now return blank data on error
        return NodeData('', '')


def write_node_file(node_data: NodeData) -> None:
    file_data = {
        'node_id': node_data.node_id,
        'password': node_data.password,
    }

    try:
        with open('data/node.json', 'r') as fh:
            fh.write(json.dumps(file_data))
    except IOError:
        with open('data/node.json', 'w') as fh:
            fh.write(json.dumps(file_data))


def node_file_exists() -> bool:
    try:
        fh = open('data/node.json', 'r')
        fh.close()
        return True
    except IOError:
        return False


def start_node() -> None:
    print('Checking if node data exists...')
    if node_file_exists():
        print('Found node data.')

        node_data = read_node_file()
        check_and_run(node_data.node_id, node_data.password)
    else:
        print('Node data not found.')

        new_data = join()
        if new_data is None:
            pass
        else:
            check_and_run(new_data.node_id, new_data.password)


async def ping() -> None:
    url = 'http://localhost:5000/v1/nodes/ping'
    headers = {'Authorization': 'dummy'}

    while True:
        await asyncio.sleep(30)
        requests.post(url, headers=headers)


def join() -> Optional[NodeData]:
    print('Joining master.')

    url = 'http://localhost:5000/v1/nodes/join'
    headers = {'Content-Type': 'application/json'}
    response = requests.post(url, headers)

    try:
        body = response.json()
        node_data = NodeData(body['node_id'], body['password'])

        print('Joined master. Assigned node ID ' + node_data.node_id)

        write_node_file(node_data)

        return node_data
    except ValueError:
        print('Failed to join master.')

        return None


def authenticate(node_id, password) -> bool:
    print('Authenticating with master.')

    url = 'http://localhost:5000/v1/nodes/auth'
    headers = {'Content-Type': 'application/json'}

    payload = {
        'node_id': node_id,
        'password': password,
    }

    response = requests.post(url, headers=headers, json=payload)

    try:
        body = response.json()
        print('Successfully authenticated with master: ' + body['token'])
        return True
    except ValueError:
        print('Invalid node credentials.')

        return False


def run_docker_container(image, command):
    client = docker.from_env()
    client.containers.run(image, command)


def get_jobs() -> List[Any]:
    url = 'http://localhost:5000/v1/jobs'
    headers = {'Content-Type': 'application/json'}

    response = requests.get(url, headers=headers)
    jobs = response.json()

    return jobs


def run_jobs(jobs):
    for i in range(len(jobs)):
        print('Running: %s and %s' % (jobs[i]['image'], jobs[i]['command']))
        run_docker_container(jobs[i]['image'], jobs[i]['command'])


def check_and_run(node_id, password):
    if authenticate(node_id, password) is True:
        create_loops()


async def poll_jobs():
    while True:
        await asyncio.sleep(10)
        jobs = get_jobs()  # type: List[Any]
        run_jobs(jobs)


def create_loops():
    loop = asyncio.get_event_loop()
    try:
        asyncio.ensure_future(poll_jobs())
        asyncio.ensure_future(ping())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
