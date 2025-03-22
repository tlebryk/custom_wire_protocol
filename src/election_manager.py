# election_manager.py
import grpc
import logging
import replica_pb2
import replica_pb2_grpc
from typing import List


class ElectionManager:
    def __init__(self, replica_addresses: List[str], local_replica_id: int):
        self.replica_addresses = replica_addresses  # List of peer replica addresses.
        self.local_replica_id = local_replica_id
        self.logger = logging.getLogger(__name__)

    def _get_stub(self, addr: str):
        """Helper method to create a gRPC stub for a given address."""
        channel = grpc.insecure_channel(addr)
        return replica_pb2_grpc.ReplicaServiceStub(channel)

    def get_peer_ids(self) -> List[int]:
        """Query all peers for their replica IDs."""
        peer_ids = []
        for addr in self.replica_addresses:
            try:
                stub = self._get_stub(addr)
                response = stub.GetReplicaID(replica_pb2.GetReplicaIDRequest())
                self.logger.info(f"Replica at {addr} reports ID {response.replica_id}")
                peer_ids.append(response.replica_id)
            except Exception as e:
                self.logger.error(f"Failed to get replica ID from {addr}: {e}")
        return peer_ids

    def elect_leader(self) -> bool:
        """Return True if this replica should become the leader (i.e. highest ID)."""
        peer_ids = self.get_peer_ids()
        all_ids = peer_ids + [self.local_replica_id]
        self.logger.info(f"Local ID: {self.local_replica_id}, All IDs: {all_ids}")
        if self.local_replica_id == max(all_ids):
            self.logger.info("This replica is elected as leader.")
            return True
        else:
            self.logger.info("This replica is not elected as leader.")
            return False
