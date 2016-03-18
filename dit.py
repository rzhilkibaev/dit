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


_default_test_timeout_seconds = 60 * 10
_execution_id = time.strftime("%Y-%m-%d_%H-%M-%S")
_test_results_directory = "test-results/" + _execution_id
_current_test_index = 1


def main(args):
    doc = load_test_file(args["--file"])
        
    print_to_console("Running test suite: " + doc["name"])
    
    client = create_docker_client(args["--docker-api-url"])
    
    log("Creating main container from image " + doc["image"])
    main_container = client.create_container(doc["image"])
    global_exit_code = 0
    try:
        log("Starting main container " + main_container.get("Id"))
        client.start(main_container)

        global _current_test_index
        
        for test in doc["tests"]:
            log("test " + str(_current_test_index))
            test_exit_code = run_test(test, client)
            if test_exit_code != 0:
                global_exit_code = 1
            _current_test_index += 1
        if global_exit_code == 0:
            print_to_console("[SUCCESS]")
        else:
            print_to_console("[FAILURE]")
    finally:
        log("Saving main container logs " + main_container.get("Id"))
        save_container_logs(main_container, "main_" + main_container.get("Id"), client)
        log("Removing main container " + main_container.get("Id"))
        client.remove_container(main_container, force=True)
        
    return global_exit_code


def load_test_file(file):
    file_to_load = file if file else "dit.yml"
    log("Loading " + file_to_load)
    with open(file_to_load) as f:
        doc = yaml.load(f)
    log("Loaded " + str(len(doc["tests"])) + " tests")
    return doc
        

def create_docker_client(docker_api_url):
    url = docker_api_url if docker_api_url else "unix://var/run/docker.sock"
    log("Creating docker client with docker api url " + url)
    return docker.Client(base_url=url)


def run_test(test, client):
    exit_code = -10
    try:
        print_to_console("Ensuring that " + test["ensures_that"])
        log("Creating test container from image " + test["image"] + " with command " + test.get("command"))
        test_container = client.create_container(test["image"], command=test.get("command"))
        try:
            log("Starting test container " + test_container.get("Id"))
            client.start(test_container)
            log("Waiting for test container " + test_container.get("Id"))
            test_timeout_seconds = test.get("timeout_s")
            test_timeout_seconds = test_timeout_seconds if test_timeout_seconds else _default_test_timeout_seconds
            exit_code = int(client.wait(test_container, timeout=test_timeout_seconds))
        finally:
            if exit_code != 0:
                print_to_console("[Fail]")
                log("Exit code " + str(exit_code))
            else:
                print_to_console("[Pass]")
            log("Saving test container logs " + test_container.get("Id"))
            save_container_logs(test_container, "test_" + str(_current_test_index) + "_" + test_container.get("Id"), client)
            log("Removing test container " + test_container.get("Id"))
            client.remove_container(test_container, force=True)
    except:
        print_to_console("Unexpected error " + sys.exc_info()[0])
        
    return exit_code
        
def save_container_logs(container, file_name, client):
    try:
        os.makedirs(_test_results_directory, exist_ok=True)
        with open(_test_results_directory + "/" + file_name + ".log", "w") as f:
            f.write(str(client.logs(container).decode("UTF-8")))
    except:
        log("Error saving container logs for container " + container)
        log(sys.exc_info()[0])

        
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