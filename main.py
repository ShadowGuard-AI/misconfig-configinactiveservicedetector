#!/usr/bin/env python3

import argparse
import json
import logging
import os
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
        bool: True if the service is active, False otherwise.  Returns False if active_services is None, so every enabled service is reported when no list is given.
    """
    if active_services is None:
        return False  # No service list: every enabled service is reported, per the help text.

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


ENABLED_STRINGS = {"true", "yes", "on", "enabled", "1"}

def is_enabled(value):
    """Return True for common enabled forms: boolean True, 1, and enabled strings."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in ENABLED_STRINGS
    return False

def collect_enabled(data, prefix=""):
    """Walk nested mappings recursively and yield (service, dotted path) for enabled leaves."""
    found = []
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                found.extend(collect_enabled(value, path))
            elif is_enabled(value):
                found.append((str(key), path))
    return found

def analyze_config_file(config_file, active_services=None):
    """
    Analyze one configuration file.

    Returns:
        tuple: (inactive_services, status) where status is "ok" when the file
        was loaded and held a non empty mapping, "empty" when it held no
        configuration, and "error" when it could not be analyzed at all.
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
                    return [], "error"
            elif file_ext == '.json':
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    logging.error(f"Error parsing JSON file {config_file}: {e}")
                    return [], "error"
            else:
                logging.error(f"Unsupported file type: {file_ext} for file {config_file}. Not analyzed.")
                return [], "error"
        if data is None or (isinstance(data, dict) and not data):
            logging.error(f"Configuration file {config_file} is empty. Nothing was analyzed.")
            return [], "empty"
        if not isinstance(data, dict):
            logging.error(f"Configuration file {config_file} does not hold a mapping. Not analyzed.")
            return [], "error"
        for service, path in collect_enabled(data):
            if not is_service_active(service, active_services):
                inactive_services.append({
                    'file': config_file,
                    'service': service,
                    'path': path,
                    'reason': 'Service is enabled in configuration but not listed as active.'
                })
    except FileNotFoundError:
        logging.error(f"Config file not found: {config_file}")
        return [], "error"
    except Exception as e:
        logging.error(f"Error analyzing config file {config_file}: {e}")
        return [], "error"
    return inactive_services, "ok"


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

    if args.output:
        resolved_output = os.path.realpath(args.output)
        for config_file in args.config_files:
            if os.path.realpath(config_file) == resolved_output:
                logging.error(f"Output path '{args.output}' is the same as config input '{config_file}'. Refusing to overwrite the input.")
                sys.exit(1)

    active_services = None
    if args.service_list:
        active_services = load_active_services(args.service_list)
        if active_services is None and args.service_list:
          logging.error(f"Failed to load active service list, exiting...")
          sys.exit(1)
    
    all_inactive_services = []
    analysis_failed = False
    analyzed_any = False
    for config_file in args.config_files:
        findings, status = analyze_config_file(config_file, active_services)
        all_inactive_services.extend(findings)
        if status == "ok":
            analyzed_any = True
        else:
            analysis_failed = True
    if not analyzed_any:
        analysis_failed = True

    if args.format == 'json':
        output_data = json.dumps(all_inactive_services, indent=4)
    else:  # args.format == 'text'
        output_data = ""
        if all_inactive_services:
            output_data += "Inactive Service Configurations Found:\n"
            for service in all_inactive_services:
                output_data += f"  File: {service['file']}\n"
                output_data += f"  Service: {service['service']}\n"
                if service.get('path'):
                    output_data += f"  Path: {service['path']}\n"
                output_data += f"  Reason: {service['reason']}\n"
                output_data += "\n"
        elif analysis_failed:
            output_data = "Analysis incomplete: one or more supplied files could not be analyzed."
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

    if analysis_failed:
        sys.exit(1)  # At least one supplied file could not be analyzed.
    if all_inactive_services:
        sys.exit(1) # Return error code if issues were found.
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()