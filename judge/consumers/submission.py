import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class SubmissionConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_name = 'submissions'
        self.room_group_name = 'submissions'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        message = json.loads(text_data)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name, message
        )
    
    async def done_submission(self, event):
        await self.send_json({
            "type": "done-submission",
            "message": event['message'],
        })
    
    async def update_submission(self, event):
        await self.send_json({
            "type": "update-submission",
            "message": event['message'],
        })


class DetailSubmission(AsyncJsonWebsocketConsumer):
    async def connect(self):
        key = self.scope['url_route']['kwargs']['key']
        self.room_group_name = 'sub_%s' % key

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        message = json.loads(text_data)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name, message
        )

    async def compile_message(self, event):
        await self.send_json({
            "type": "compile-message",
        })
    
    async def compile_error(self, event):
        await self.send_json({
            "type": "compile-error",
            "message": event['message'],
        })

    async def internal_error(self, event):
        await self.send_json({
            "type": "internal-error",
        })
    
    async def aborted_submission(self, event):
        await self.send_json({
            "type": "aborted-submission",
        })
    
    async def test_case(self, event):
        await self.send_json({
            "type": "test-case",
            "message": event['message']
        })
    
    async def grading_begin(self, event):
        await self.send_json({
            "type": "grading-begin",
        })

    async def grading_end(self, event):
        await self.send_json({
            "type": "grading-end",
            "message": event['message'],
        })

    async def processing(self, event):
        await self.send_json({
            "type": "processing"
        })