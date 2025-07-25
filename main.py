#!/usr/bin/env python3

import argparse
import json
import logging
import os
import subprocess
import sys
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_argparse():
    """
    Sets up the argument parser for the command-line interface.
    """
    parser = argparse.ArgumentParser(description='Detects configurations that enable inactive services.')
    parser.add_argument('config_files', nargs='+', help='Path to configuration file(s) to analyze.')
    parser.add_argument('--service-list', help='Path to a file containing a list of known active services (one service name per line).  If not provided, all enabled services are considered potentially inactive.', required=False)
    parser.add_argument('--output', help='Path to output file (optional).  If not provided, output is printed to stdout.', required=False)
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format (text or json). Defaults to text.')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging.')
    return parser

def is_service_active(service_name, active_services):
    """
    Checks if a service is considered active.

    Args:
        service_name (str): The name of the service.
        active_services (set): A set of known active service names.

    Returns:
        bool: True if the service is active, False otherwise.  Returns True if active_services is None (meaning we're not checking).
    """
    if active_services is None:
        return True  # If no service list is provided, assume all are active

    return service_name in active_services

def load_active_services(service_list_file):
    """
    Loads a list of active service names from a file.

    Args:
        service_list_file (str): Path to the file containing the service names.

    Returns:
        set: A set of active service names.  Returns None if the file is invalid or empty
    """
    try:
        with open(service_list_file, 'r') as f:
            services = {line.strip() for line in f if line.strip()} # Use a set for faster lookups and strip whitespace
        if not services:
            logging.warning(f"Active service list file '{service_list_file}' is empty. All enabled services will be considered potentially inactive.")
            return None
        return services
    except FileNotFoundError:
        logging.error(f"Active service list file not found: {service_list_file}")
        return None
    except Exception as e:
        logging.error(f"Error reading active service list file: {e}")
        return None


def analyze_config_file(config_file, active_services=None):
    """
    Analyzes a configuration file to detect inactive service configurations.

    Args:
        config_file (str): Path to the configuration file.
        active_services (set): A set of known active service names.

    Returns:
        list: A list of dictionaries, each containing details about an inactive service configuration.
    """
    inactive_services = []
    try:
        file_ext = os.path.splitext(config_file)[1].lower()

        with open(config_file, 'r') as f:
            if file_ext in ['.yaml', '.yml']:
                try:
                    data = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    logging.error(f"Error parsing YAML file {config_file}: {e}")
                    return []
            elif file_ext == '.json':
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    logging.error(f"Error parsing JSON file {config_file}: {e}")
                    return []
            else:
                logging.warning(f"Unsupported file type: {file_ext} for file {config_file}. Skipping.")
                return []

        # Basic logic:  This is a simplified example.  Adapt to your specific config structures.
        # Assume the config is a dictionary and services are keys with boolean values (True=enabled).
        if isinstance(data, dict):
            for service, enabled in data.items():
                if isinstance(enabled, bool) and enabled:  # Check if the service is enabled (True)
                    if not is_service_active(service, active_services):
                        inactive_services.append({
                            'file': config_file,
                            'service': service,
                            'reason': 'Service is enabled in configuration but not listed as active.'
                        })
    except FileNotFoundError:
        logging.error(f"Config file not found: {config_file}")
    except Exception as e:
        logging.error(f"Error analyzing config file {config_file}: {e}")

    return inactive_services


def main():
    """
    Main function to execute the misconfiguration detector.
    """
    parser = setup_argparse()
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Debug mode enabled.")

    if not args.config_files:
        logging.error("No configuration files specified.")
        parser.print_help()
        sys.exit(1)

    active_services = None
    if args.service_list:
        active_services = load_active_services(args.service_list)
        if active_services is None and args.service_list:
          logging.error(f"Failed to load active service list, exiting...")
          sys.exit(1)
    
    all_inactive_services = []
    for config_file in args.config_files:
        all_inactive_services.extend(analyze_config_file(config_file, active_services))

    if args.format == 'json':
        output_data = json.dumps(all_inactive_services, indent=4)
    else:  # args.format == 'text'
        output_data = ""
        if all_inactive_services:
            output_data += "Inactive Service Configurations Found:\n"
            for service in all_inactive_services:
                output_data += f"  File: {service['file']}\n"
                output_data += f"  Service: {service['service']}\n"
                output_data += f"  Reason: {service['reason']}\n"
                output_data += "\n"
        else:
            output_data = "No inactive service configurations found."

    if args.output:
        try:
            with open(args.output, 'w') as outfile:
                outfile.write(output_data)
            logging.info(f"Output written to: {args.output}")
        except Exception as e:
            logging.error(f"Error writing to output file: {e}")
            sys.exit(1)
    else:
        print(output_data)

    if all_inactive_services:
        sys.exit(1) # Return error code if issues were found.
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()