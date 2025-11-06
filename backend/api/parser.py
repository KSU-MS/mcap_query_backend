#this is just a test before writing the api 
#so the goal is to just parse the mcap summary , which will give all the avilable channels , and also the time length of the log and maybe file size 
#final boss also parse the gps cords and , time , and date

#/Users/pettruskonnoth/Documents/mcap_logs/08_14_2025_23_10_40-rec.mcap

import sys
from mcap_protobuf.decoder import DecoderFactory
from mcap.reader import make_reader
import datetime

class Parser:
    @staticmethod
    def parse_stuff(path):
        with open(path, "rb") as f:
            reader = make_reader(f, decoder_factories=[DecoderFactory()])
            summary = reader.get_summary()
            available_channels = summary.channels
            
            # Get channels list
            channels = []
            for value in available_channels.values():
                dict_to_val = str(value)
                split_channel = dict_to_val.split("topic='")[1]
                topic = split_channel.split("'")[0]
                channels.append(topic)

            # Get timestamps and duration
            msg_start = (summary.statistics.message_start_time)/(1e9)
            msg_end = (summary.statistics.message_end_time)/(1e9)
            duration = msg_end - msg_start
            date = datetime.datetime.fromtimestamp(int(msg_start)).strftime('%Y-%m-%d %H:%M:%S')

            # Return data as dictionary
            return {
                "channels": channels,
                "channel_count": len(channels),
                "start_time": msg_start,
                "end_time": msg_end,
                "duration": duration,
                "formatted_date": date
            }

"""
class Parser():

    def parse_stuff(path):
        with open(path,"rb") as f:
            reader = make_reader(f,decoder_factories=[DecoderFactory()])
            summmary = reader.get_summary()
            avilable_channels = summmary.channels
            print("balls\n")

            count = 0
            #for loop the get the channels from dict
            for value in avilable_channels.values():
                #splitting just the channel
                dictToval = str(value)
                split_channel = dictToval.split("topic='")[1]
                topic = split_channel.split("'")[0]
                print(topic)
                count+=1
            print(f"\nNumber of channels:{count}\n")


            msg_start = (summmary.statistics.message_start_time)/(1e9)
            end = (summmary.statistics.message_end_time)/(1e9)

            duration = end - msg_start

            log_duration = str(datetime.timedelta)

            date = datetime.datetime.fromtimestamp(int(msg_start)).strftime('%Y-%m-%d %H:%M:%S')
            print(date)
            

            print(f"unix time stamp {msg_start} in seconds")

            #for schema , channel , message , proto_msg in reader.iter_decoded_messages(topics="evelogger_vectornav_position_data"):
                #print(proto_msg)
        


#path = "/Users/pettruskonnoth/Documents/mcap_logs/09_25_2025_23_38_08-rec.mcap"


"""