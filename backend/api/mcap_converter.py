"""
MCAP to CSV/LD Converter Module

Converts MCAP files to CSV format using Protobuf decoding.
Matches mcap_parser format specifications for TVN, OMNI, and LD formats.
"""
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from mcap_protobuf.decoder import DecoderFactory
from mcap.reader import make_reader


class McapToCsvConverter:
    """
    Converts MCAP files to CSV/LD format with Protobuf decoding.
    Matches mcap_parser format specifications.
    """
    
    def __init__(self):
        self.decoder_factory = DecoderFactory()
    
    def convert_to_csv(self, mcap_path: str, output_path: str, format: str = 'omni') -> str:
        """
        Convert MCAP file to CSV/LD format.
        
        Args:
            mcap_path: Path to input MCAP file
            output_path: Path where output file will be written
            format: Format profile ('omni', 'tvn', or 'ld')
            
        Returns:
            Path to the created output file
            
        Raises:
            FileNotFoundError: If MCAP file doesn't exist
            ValueError: If format is invalid
            Exception: For other conversion errors
        """
        mcap_path = Path(mcap_path)
        if not mcap_path.exists():
            raise FileNotFoundError(f"MCAP file not found: {mcap_path}")
        
        if format not in ['omni', 'tvn', 'ld']:
            raise ValueError(f"Invalid format: {format}. Must be 'omni', 'tvn', or 'ld'")
        
        # Ensure output directory exists
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(mcap_path, 'rb') as f:
                # Parse MCAP file using mcap_parser approach
                data, topics = self._parse_mcap(f)
                
                # Write based on format
                if format == 'tvn':
                    self._write_csv_tvn(output_path, data)
                elif format == 'omni':
                    self._write_csv_omni(output_path, data, topics)
                elif format == 'ld':
                    self._write_ld(output_path, data, topics)
                
        except Exception as e:
            raise Exception(f"Error converting MCAP to {format.upper()}: {str(e)}") from e
        
        return str(output_path)
    
    def _parse_mcap(self, file) -> Tuple[List[List[List[Any]]], List[str]]:
        """
        Parse MCAP file using mcap_parser approach.
        Extracts only top-level Protobuf fields (no nested flattening).
        
        Args:
            file: Open file handle to MCAP file
            
        Returns:
            Tuple of (data, topics) where:
            - data: List of message data, each message is a list of [timestamp, field_name, field_value] tuples
            - topics: List of unique field names found across all messages
        """
        reader = make_reader(file, decoder_factories=[self.decoder_factory])
        
        data = []
        topics = []
        
        # Iterate over each message
        for schema, channel, message, proto_msg in reader.iter_decoded_messages():
            # Get field names from Protobuf descriptor (top-level only)
            field_names = [field.name for field in proto_msg.DESCRIPTOR.fields]
            
            topic_data = []
            
            # Extract each field value
            for name in field_names:
                # Track unique topics/fields
                if name not in topics:
                    topics.append(name)
                
                # Get field value
                try:
                    field_value = getattr(proto_msg, name)
                    # Convert to string representation
                    value_str = self._convert_value(field_value)
                    
                    # Structure: [timestamp (nanoseconds), field_name, field_value]
                    topic_data.append([
                        message.log_time,  # Keep in nanoseconds like mcap_parser
                        name,
                        value_str
                    ])
                except Exception as e:
                    # Skip fields that can't be accessed
                    print(f"Warning: Could not process field {name}: {e}")
                    continue
            
            data.append(topic_data)
        
        return data, topics
    
    def _convert_value(self, value: Any) -> str:
        """
        Convert a Protobuf field value to a string representation.
        
        Args:
            value: Value to convert
            
        Returns:
            String representation of the value
        """
        if value is None:
            return ''
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, bytes):
            # For binary data, encode as hex or skip
            return value.hex() if len(value) < 100 else '[binary data]'
        elif isinstance(value, list):
            # Handle repeated fields - convert to comma-separated string
            return ','.join(str(self._convert_value(item)) for item in value)
        else:
            return str(value)
    
    def _write_csv_tvn(self, output_path: Path, data: List[List[List[Any]]]) -> None:
        """
        Write CSV in TVN format (matching mcap_parser).
        Format: Time, Name, Value columns - one row per field value.
        
        Args:
            output_path: Path to output CSV file
            data: Parsed MCAP data (list of messages, each containing [timestamp, field_name, field_value] tuples)
        """
        with open(output_path, 'w', newline='', encoding='utf-8', buffering=1) as file:
            writer = csv.writer(file)
            
            # Write header: Time, Name, Value
            writer.writerow(["Time", "Name", "Value"])
            
            # Iterate through all messages and their field values
            for point in data:
                for val in point:
                    # val is [timestamp, field_name, field_value]
                    writer.writerow(val)
            
            file.flush()
    
    def _write_csv_omni(self, output_path: Path, data: List[List[List[Any]]], topics: List[str]) -> None:
        """
        Write CSV in OMNI format (matching mcap_parser).
        Format: Time column + one column per topic/field, with values aligned by timestamp.
        
        Args:
            output_path: Path to output CSV file
            data: Parsed MCAP data (list of messages, each containing [timestamp, field_name, field_value] tuples)
            topics: List of unique field names (topics)
        """
        with open(output_path, 'w', newline='', encoding='utf-8', buffering=1) as file:
            writer = csv.writer(file)
            
            # Build header: Time + all topics
            header = ["Time"] + topics
            writer.writerow(header)
            
            # Group data by timestamp
            timestamp_groups = {}
            for point in data:
                if not point:
                    continue
                
                # Get timestamp from first field in this message
                timestamp = point[0][0]
                
                # Initialize timestamp group if not exists
                if timestamp not in timestamp_groups:
                    timestamp_groups[timestamp] = {}
                
                # Add all field values for this timestamp
                for val in point:
                    field_name = val[1]
                    field_value = val[2]
                    timestamp_groups[timestamp][field_name] = field_value
            
            # Write rows sorted by timestamp
            for timestamp in sorted(timestamp_groups.keys()):
                row = [timestamp]
                topic_values = timestamp_groups[timestamp]
                
                # Add value for each topic (None if not present for this timestamp)
                for topic in topics:
                    if topic in topic_values:
                        row.append(topic_values[topic])
                    else:
                        row.append(None)
                
                writer.writerow(row)
            
            file.flush()
    
    def _write_ld(self, output_path: Path, data: List[List[List[Any]]], topics: List[str]) -> None:
        """
        Write LD format (placeholder - matches mcap_parser current state).
        
        Args:
            output_path: Path to output file
            data: Parsed MCAP data
            topics: List of unique field names
        """
        # Placeholder implementation (mcap_parser currently just prints "test")
        # For now, write a simple text file indicating LD format
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write("# LD Format (placeholder)\n")
            file.write(f"# This format is not yet fully implemented\n")
            file.write(f"# Data points: {len(data)}\n")
            file.write(f"# Topics: {len(topics)}\n")
            file.write(f"# Topics: {', '.join(topics)}\n")
