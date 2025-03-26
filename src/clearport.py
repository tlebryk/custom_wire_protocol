import psutil


def kill_process_on_ports(ports):
    """Cycle through all given ports and kill any processes using them."""
    for port in ports:
        print(f"Checking port: {port}")
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                for conn in proc.connections(kind="inet"):
                    # Check if the local address port matches our target port
                    if conn.laddr.port == port:
                        print(
                            f"Killing process {proc.pid} ({proc.name()}) using port {port}"
                        )
                        proc.kill()
                        # Once killed, no need to check more connections for this process
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                print(f"Skipping process: {e}")


if __name__ == "__main__":
    # List of all ports used in our system: load balancers and replicas.
    ports_to_check = [50051, 50054, 50055, 50052, 50053, 50056]
    kill_process_on_ports(ports_to_check)
