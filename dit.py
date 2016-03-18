#!/usr/bin/env python3
"""
Usage:
       dit [options]

Options:
    --help                   show this help
    --docker-api-url=<url>   docker api url (default: unix://var/run/docker.sock)
    --file=<filename>        test suite file (default: dit.yml)
"""
import docker
import docopt
import os
import time
import yaml
import sys
import traceback


_default_test_timeout_seconds = 60 * 1
_execution_id = time.strftime("%Y-%m-%d_%H-%M-%S")
_test_results_directory = "test-results/" + _execution_id


def main(args):
    global_exit_code = 0
    file_to_load = args["--file"] if args["--file"] else "dit.yml"
    log("Loading " + file_to_load)
    current_suite_index = 1
    with open(file_to_load) as f:
        for doc in yaml.load_all(f):
            suite_exit_code = run_test_suite(args, doc, current_suite_index)
            if suite_exit_code:
                global_exit_code = 1
            current_suite_index += 1
        if global_exit_code == 0:
            print_to_console("[SUCCESS]")
        else:
            print_to_console("[FAILURE]")
    return global_exit_code

def run_test_suite(args, doc, current_suite_index):
    print_to_console(doc["name"])
    
    client = create_docker_client(args["--docker-api-url"])
    
    log("Creating main container from image " + doc["image"])
    main_container = client.create_container(doc["image"], environment=doc.get("env"))
    suite_exit_code = 0
    try:
        start_main_container(main_container, doc, client)

        current_test_index = 1
        
        for test in doc["tests"]:
            log("test " + str(current_test_index))
            test_exit_code = run_test(test, main_container, current_suite_index, current_test_index, client)
            if test_exit_code != 0:
                suite_exit_code = 1
            current_test_index += 1
    finally:
        log("Saving main container logs " + main_container.get("Id"))
        save_container_logs(main_container, "suite_" + str(current_suite_index) + "_" + main_container.get("Id"), client)
        log("Removing main container " + main_container.get("Id"))
        client.remove_container(main_container, force=True)
        
    return suite_exit_code

def load_test_file(file):
    file_to_load = file if file else "dit.yml"
    log("Loading " + file_to_load)
    with open(file_to_load) as f:
        docs = yaml.load_all(f)
        for doc in docs:
            print(str(doc))
    return docs
        

def create_docker_client(docker_api_url):
    url = docker_api_url if docker_api_url else "unix://var/run/docker.sock"
    log("Creating docker client with docker api url " + url)
    return docker.Client(base_url=url)


def start_main_container(main_container, doc, client):
    log("Starting main container " + main_container.get("Id"))
    client.start(main_container)
    ready_message = doc.get("ready_message")
    if ready_message:
        log("waiting for ready message " + ready_message)
        for line in client.logs(main_container, stream=True):
            if ready_message in line.decode("UTF-8"):
                break
    wait_s = doc.get("wait_s")
    if wait_s:
        log("waiting for " + str(wait_s) + " seconds")
        time.sleep(wait_s)


def run_test(test, main_container, current_suite_index, current_test_index, client):
    exit_code = -10
    try:
        print_to_console("    " + test["ensures_that"])
        log("Creating test container from image " + test["image"] + " with command " + test.get("command"))
        test_container = client.create_container(test["image"], command=test.get("command"))
        try:
            log("Starting test container " + test_container.get("Id"))
            client.start(test_container, links={main_container["Id"]:"main"})
            log("Waiting for test container " + test_container.get("Id"))
            test_timeout_seconds = test.get("timeout_s")
            test_timeout_seconds = test_timeout_seconds if test_timeout_seconds else _default_test_timeout_seconds
            exit_code = int(client.wait(test_container, timeout=test_timeout_seconds))
        finally:
            if exit_code != 0:
                print_to_console("    [Fail]")
                log("Exit code " + str(exit_code))
            else:
                print_to_console("    [Pass]")
            log("Saving test container logs " + test_container.get("Id"))
            save_container_logs(test_container, "suite_" + str(current_suite_index) + "_test_" + str(current_test_index) + "_" + test_container.get("Id"), client)
            log("Removing test container " + test_container.get("Id"))
            client.remove_container(test_container, force=True)
    except:
        print_to_console("    Unexpected error " + str(sys.exc_info()))
        
    return exit_code
        
def save_container_logs(container, file_name, client):
    try:
        os.makedirs(_test_results_directory, exist_ok=True)
        with open(_test_results_directory + "/" + file_name + ".log", "w") as f:
            f.write(str(client.logs(container).decode("UTF-8")))
    except:
        log("Error saving container logs for container " + container)
        log(str(sys.exc_info()))

        
def print_to_console(msg):
    print(msg)
    log(msg)


def log(msg):
    os.makedirs(_test_results_directory, exist_ok=True)
    with open(_test_results_directory + "/dit.log", "a") as f:
        f.write(msg + "\n")


if __name__ == "__main__":
    args = docopt.docopt(__doc__, version="Docker Image Tester version 0.1")
    try:
        global_exit_code = main(args)
    except:
        traceback.print_exc()
        global_exit_code = 1

    exit(global_exit_code)