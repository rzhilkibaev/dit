#!/usr/bin/env python3
import yaml
import docker

def main():
    with open("test.yml", "r") as f:
        doc = yaml.load(f)
        
    print(doc["name"])
    
    # run image
    client = docker.Client(base_url="unix://var/run/docker.sock")
    container = client.create_container(image=doc["image"])
    try:
        print("Created container " + str(container))
        # run tests
    finally:
        # remove mage
        client.remove_container(container, force=True)
    
    
if __name__ == "__main__":
    main()