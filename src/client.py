# grpc_client.py
import grpc
import protocols_pb2
import protocols_pb2_grpc


class GRPCClient:
    def __init__(self, host="localhost", port=50051):
        print("initializing grpc client")
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        print("channel created")
        self.stub = protocols_pb2_grpc.MessagingServiceStub(self.channel)
        print("stub created")

    def register(self, username, password):
        request = protocols_pb2.RegisterRequest(username=username, password=password)
        return self.stub.Register(request)

    def login(self, username, password):
        request = protocols_pb2.LoginRequest(username=username, password=password)
        return self.stub.Login(request)

    def send_message(self, receiver, message):
        request = protocols_pb2.SendMessageRequest(receiver=receiver, message=message)
        return self.stub.SendMessage(request)

    def echo(self, message):
        request = protocols_pb2.EchoRequest(message=message)
        return self.stub.Echo(request)

    # Add other methods as needed for your routes...


if __name__ == "__main__":
    client = GRPCClient()
    # Example: Test echo (ping)
    response = client.echo("ping")
    print("Echo response:", response)
