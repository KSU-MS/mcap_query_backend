"""
MCAP to CSV Converter Module

Converts MCAP files to CSV format using Protobuf decoding.
Supports different CSV format profiles (omni, tvn).
"""
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional
from mcap_protobuf.decoder import DecoderFactory
from mcap.reader import make_reader


class McapToCsvConverter:
    """
    Converts MCAP files to CSV format with Protobuf decoding.
    """
    
    def __init__(self):
        self.decoder_factory = DecoderFactory()
    
    def convert_to_csv(self, mcap_path: str, output_path: str, format: str = 'omni') -> str:
        """
        Convert MCAP file to CSV format.
        
        Args:
            mcap_path: Path to input MCAP file
            output_path: Path where CSV file will be written
            format: CSV format profile ('omni' or 'tvn')
            
        Returns:
            Path to the created CSV file
            
        Raises:
            FileNotFoundError: If MCAP file doesn't exist
            ValueError: If format is invalid
            Exception: For other conversion errors
        """
        mcap_path = Path(mcap_path)
        if not mcap_path.exists():
            raise FileNotFoundError(f"MCAP file not found: {mcap_path}")
        
        if format not in ['omni', 'tvn']:
            raise ValueError(f"Invalid format: {format}. Must be 'omni' or 'tvn'")
        
        # Ensure output directory exists
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read MCAP file and collect all messages
        messages_data = []
        all_field_names = set()
        
        try:
            with open(mcap_path, 'rb') as f:
                reader = make_reader(f, decoder_factories=[self.decoder_factory])
                
                # First pass: collect all messages and discover all field names
                for schema, channel, message, proto_msg in reader.iter_decoded_messages():
                    # Convert timestamp from nanoseconds to seconds
                    timestamp = message.log_time / 1e9
                    topic = channel.topic
                    
                    # Flatten Protobuf message
                    flattened = self._flatten_protobuf_message(proto_msg)
                    
                    # Add timestamp and topic to flattened data
                    row_data = {
                        'timestamp': timestamp,
                        'topic': topic,
                        **flattened
                    }
                    
                    messages_data.append(row_data)
                    all_field_names.update(flattened.keys())
                
                # Generate CSV headers based on format
                headers = self._get_csv_headers(all_field_names, format)
                
                # Write messages to CSV
                self._write_messages_to_csv(messages_data, output_path, headers)
                
        except Exception as e:
            raise Exception(f"Error converting MCAP to CSV: {str(e)}") from e
        
        return str(output_path)
    
    def _flatten_protobuf_message(self, msg: Any, prefix: str = '') -> Dict[str, Any]:
        """
        Recursively flatten a Protobuf message into a dictionary.
        
        Args:
            msg: Protobuf message object
            prefix: Prefix for nested field names (for nested structures)
            
        Returns:
            Dictionary with flattened field names as keys
        """
        flattened = {}
        
        if not hasattr(msg, 'DESCRIPTOR'):
            # Not a Protobuf message, return as-is
            return {prefix: msg} if prefix else {}
        
        # Iterate through all fields in the Protobuf message
        for field in msg.DESCRIPTOR.fields:
            field_name = field.name
            full_field_name = f"{prefix}.{field_name}" if prefix else field_name
            
            try:
                field_value = getattr(msg, field_name)
                
                # Handle different field types
                if field_value is None:
                    continue
                
                # Handle repeated fields (lists)
                if field.label == field.LABEL_REPEATED:
                    if len(field_value) == 0:
                        # Empty list - store as empty string
                        flattened[full_field_name] = ''
                    elif len(field_value) == 1:
                        # Single item - flatten it
                        item = field_value[0]
                        if hasattr(item, 'DESCRIPTOR'):
                            # Nested message in list
                            nested = self._flatten_protobuf_message(item, full_field_name)
                            flattened.update(nested)
                        else:
                            # Primitive value in list
                            flattened[full_field_name] = self._convert_value(item)
                    else:
                        # Multiple items - store as comma-separated string
                        values = [self._convert_value(item) for item in field_value]
                        flattened[full_field_name] = ','.join(str(v) for v in values)
                
                # Handle nested messages
                elif hasattr(field_value, 'DESCRIPTOR'):
                    nested = self._flatten_protobuf_message(field_value, full_field_name)
                    flattened.update(nested)
                
                # Handle primitive values
                else:
                    flattened[full_field_name] = self._convert_value(field_value)
                    
            except Exception as e:
                # Skip fields that can't be accessed
                print(f"Warning: Could not process field {full_field_name}: {e}")
                continue
        
        return flattened
    
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
        else:
            return str(value)
    
    def _get_csv_headers(self, field_names: set, format: str) -> List[str]:
        """
        Generate CSV headers based on format profile.
        
        Args:
            field_names: Set of all discovered field names
            format: Format profile ('omni' or 'tvn')
            
        Returns:
            List of CSV column headers
        """
        # Base headers: timestamp and topic
        headers = ['timestamp', 'topic']
        
        # Sort field names for consistent column order
        sorted_fields = sorted(field_names)
        
        if format == 'omni':
            # Omni format: include all fields
            headers.extend(sorted_fields)
        elif format == 'tvn':
            # TVN format: filter for VectorNav-related fields
            tvn_fields = [f for f in sorted_fields if 'vectornav' in f.lower() or 'tvn' in f.lower()]
            headers.extend(tvn_fields)
        else:
            # Default: include all fields
            headers.extend(sorted_fields)
        
        return headers
    
    def _write_messages_to_csv(self, messages_data: List[Dict[str, Any]], output_path: Path, headers: List[str]) -> None:
        """
        Write flattened messages to CSV file.
        
        Args:
            messages_data: List of dictionaries containing message data
            output_path: Path to output CSV file
            headers: List of CSV column headers
        """
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            
            for message in messages_data:
                # Ensure all header columns exist in message dict
                row = {header: message.get(header, '') for header in headers}
                writer.writerow(row)
