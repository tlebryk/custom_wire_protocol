# election_manager.py
import grpc
import logging
from typing import List, Dict, Tuple

import replica_pb2
import replica_pb2_grpc


class ElectionManager:
    def __init__(self, replica_addresses: List[str], local_replica_id: int):
        self.replica_addresses = replica_addresses  # List of peer replica addresses.
        self.local_replica_id = local_replica_id
        self.local_address = None  # Will be populated when needed
        self.logger = logging.getLogger(__name__)

        # Configure gRPC with appropriate timeouts for network communication
        self.timeout = 3  # 3 seconds timeout for gRPC calls

    def _get_stub(self, addr: str):
        """Helper method to create a gRPC stub for a given address."""
        channel = grpc.insecure_channel(addr)
        return replica_pb2_grpc.ReplicaServiceStub(channel), channel

    def _close_channel(self, channel):
        """Helper method to close a gRPC channel."""
        if channel:
            try:
                channel.close()
            except Exception as e:
                self.logger.warning(f"Error closing channel: {e}")

    def get_peer_ids(self) -> Dict[str, int]:
        """
        Query all peers for their replica IDs.

        Returns:
            Dict mapping replica address to its ID
        """
        peer_ids = {}
        for addr in self.replica_addresses:
            channel = None
            try:
                stub, channel = self._get_stub(addr)
                response = stub.GetReplicaID(
                    replica_pb2.GetReplicaIDRequest(), timeout=self.timeout
                )
                self.logger.info(f"Replica at {addr} reports ID {response.replica_id}")
                peer_ids[addr] = response.replica_id

                # If this is our address, store it
                if response.replica_id == self.local_replica_id:
                    self.local_address = addr

            except grpc.RpcError as rpc_error:
                if rpc_error.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                    self.logger.warning(f"Timeout getting ID from {addr}")
                else:
                    self.logger.warning(
                        f"RPC error getting ID from {addr}: {rpc_error.code()}"
                    )
            except Exception as e:
                self.logger.error(f"Failed to get replica ID from {addr}: {e}")
            finally:
                self._close_channel(channel)

        return peer_ids

    def elect_leader(self) -> bool:
        """
        Return True if this replica should become the leader (i.e. highest ID).

        The leader election strategy is to select the replica with the highest ID
        among all reachable replicas.
        """
        peer_id_map = self.get_peer_ids()

        # Filter out any unavailable replicas
        available_ids = [(addr, id) for addr, id in peer_id_map.items()]

        if not available_ids:
            self.logger.warning("No replicas (including self) are reachable!")
            # If we can't reach anyone including ourselves, don't become leader
            return False

        # Find the replica with the highest ID
        highest_id_addr, highest_id = max(available_ids, key=lambda x: x[1])

        # Check if we are the highest
        if highest_id == self.local_replica_id:
            self.logger.info(
                f"This replica (ID={self.local_replica_id}) is elected as leader."
            )
            return True
        else:
            self.logger.info(
                f"This replica is not elected as leader. Leader is at {highest_id_addr} with ID {highest_id}"
            )
            return False

    def notify_election_result(self, won: bool) -> None:
        """
        Notify other replicas about the election result.
        This is useful to avoid multiple replicas transitioning to leader.

        Args:
            won: True if this replica won the election
        """
        if not won:
            return  # Only notify if we won

        for addr in self.replica_addresses:
            if addr == self.local_address:
                continue  # Skip self

            channel = None
            try:
                stub, channel = self._get_stub(addr)
                response = stub.NotifyElectionResult(
                    replica_pb2.ElectionResultNotification(
                        leader_id=self.local_replica_id,
                        leader_address=self.local_address,
                    ),
                    timeout=self.timeout,
                )
                self.logger.info(f"Notified {addr} about election result")
            except Exception as e:
                self.logger.error(f"Failed to notify {addr} about election result: {e}")
            finally:
                self._close_channel(channel)
