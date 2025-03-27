import grpc

import logging


# deprecated for replica server milestone.
# legacy for testing size of packets.
@DeprecationWarning
class SizeLoggingServerInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        handler = continuation(handler_call_details)
        if handler is None:
            return None

        def new_behavior(request, context):
            # Log request size
            req_size = len(request.SerializeToString())
            logging.info(f"Server received request of size: {req_size} bytes")
            response = handler.unary_unary(request, context)
            # Log response size
            resp_size = len(response.SerializeToString())
            logging.info(f"Server sending response of size: {resp_size} bytes")
            return response

        if handler.unary_unary:
            return grpc.unary_unary_rpc_method_handler(new_behavior)
        # Add similar wrappers for other RPC types if needed.
        return handler
