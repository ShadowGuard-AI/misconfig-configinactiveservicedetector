![Banner](banner.png)

# misconfig-ConfigInactiveServiceDetector
Detects configurations that enable services which are currently inactive or not being used, suggesting potential security vulnerabilities or resource wastage. - Focused on Check for misconfigurations in configuration files or infrastructure definitions

## Install
`git clone https://github.com/ShadowGuardAI/misconfig-configinactiveservicedetector`

## Usage
`python3 main.py config.yaml [config2.json ...] [--service-list active.txt] [--output report.txt] [--format text|json] [--debug]`

## Parameters
- `config_files`: One or more configuration files to analyze (YAML or JSON, positional, required). Services may be flat keys or nested under mappings such as a `services` key. A value counts as enabled when it is boolean true, 1, or one of the strings "true", "yes", "on", "enabled", or "1".
- `-h`: Show help message and exit
- `--service-list`: Path to a file listing known active services, one per line. If not provided, every enabled service is reported as potentially inactive.
- `--output`: Path to the output file. It must not be the same file as a configuration input; such a run is refused at exit 1 and the input is left unchanged.
- `--format`: Output format, text or json. Defaults to text.
- `--debug`: Enable debug logging.

A run exits 1 when findings are reported, and also when any supplied file is missing, malformed, unsupported, or empty, because nothing was analyzed for that file. A genuine clean run over real content exits 0.

## License
Copyright (c) ShadowGuardAI
