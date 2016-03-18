#!/usr/bin/env python3
import docker
import yaml


def main():
    with open("test.yml", "r") as f:
        doc = yaml.load(f)
        
    print(doc["name"])
    
    # run image
    client = docker.Client(base_url="unix://var/run/docker.sock")
    container = client.create_container(image=doc["image"])
    try:
        print("Created container " + str(container["Id"]))
        print("Testing that:")
        for test in doc["tests"]:
            run_test(test, client)
        # run tests
    finally:
        # remove image
        client.remove_container(container, force=True)
    

def run_test(test, client):
    try:
        print(test["ensures_that"])
        container = client.create_container(image=test["image"], command=test.get("command"))
        try:
            client.start(container)
            exit_code = client.wait(container, timeout=_test_timeout_seconds)
            if exit_code != 0:
                print("[Fail]")
            else:
                print("[Pass]")
        finally:
#             print(str(client.logs(container)))
            client.remove_container(container, force=True)
        
    except:
        print("Unexpected error")

_test_timeout_seconds=60*10

if __name__ == "__main__":
    main()