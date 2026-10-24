# NetWatch Viva Questions and Answers

62 questions with simple answers.

**Q1. What is network monitoring?**

A. Network monitoring means continuously checking a network to see if it is working properly and to notice problems quickly. NetWatch checks connectivity, delay, packet loss, DNS, bandwidth and services.

**Q2. Why did you select this project?**

A. Network problems such as 'internet is slow' are common in labs, hostels and offices, and people need a simple way to find where the problem is. This project solves a real problem and uses many Computer Networks concepts.

**Q3. What problem does NetWatch solve?**

A. It shows in one dashboard whether the problem is the local connection, the gateway, DNS, the internet, high latency, packet loss or a specific service.

**Q4. What is latency?**

A. Latency is the time a packet takes to travel to a destination and get a reply, measured in milliseconds. NetWatch reads it from ping results.

**Q5. What is packet loss?**

A. Packet loss is the percentage of packets that are sent but do not get a reply. Packet loss % = (sent - received) / sent x 100.

**Q6. What is bandwidth?**

A. Bandwidth is the maximum amount of data a link can carry per second, for example 100 Mbps.

**Q7. What is throughput?**

A. Throughput is the actual data rate achieved right now. NetWatch shows throughput (traffic on the interface), not the maximum bandwidth.

**Q8. What is ping?**

A. Ping is a tool that sends ICMP echo request packets to a host and waits for echo replies. It shows if the host is reachable and the round-trip time.

**Q9. What is ICMP?**

A. ICMP (Internet Control Message Protocol) is used for network control and error messages. Ping uses ICMP echo request and echo reply.

**Q10. What is DNS?**

A. DNS (Domain Name System) converts names like example.com into IP addresses.

**Q11. What is TCP?**

A. TCP is a connection-oriented, reliable transport protocol. It sets up a connection with a three-way handshake and makes sure data arrives in order.

**Q12. What is UDP?**

A. UDP is a connectionless transport protocol. It is faster and simpler than TCP but does not guarantee delivery. DNS usually uses UDP.

**Q13. What is a TCP port?**

A. A port is a 16-bit number (0 to 65535) that identifies a service on a host, such as 80 for HTTP and 443 for HTTPS.

**Q14. What is a socket?**

A. A socket is one end of a network connection, made of an IP address and a port. Python's socket module lets programs create sockets.

**Q15. What is localhost?**

A. localhost is the name for this same computer. Its IPv4 address is 127.0.0.1. Traffic to it never leaves the computer.

**Q16. What is an IP address?**

A. An IP address is a unique logical address given to a device on a network, for example 192.168.1.10.

**Q17. What is a subnet mask?**

A. A subnet mask tells which part of an IP address is the network and which part is the host. For example 255.255.255.0.

**Q18. What is a gateway?**

A. A gateway is a device that connects one network to another. In a home or lab it is usually the router.

**Q19. What is a default gateway?**

A. The default gateway is the router your computer sends packets to when the destination is outside the local network.

**Q20. What is a network interface?**

A. An interface is the hardware or virtual adapter that connects a computer to a network, such as Wi-Fi or Ethernet.

**Q21. What is Flask?**

A. Flask is a small Python web framework. NetWatch uses it to serve the dashboard page and the JSON API.

**Q22. Why Python?**

A. Python is simple, has a strong standard library for networking (socket, urllib, subprocess) and has psutil for system information. It is easy to explain and demonstrate.

**Q23. Why psutil?**

A. psutil gives real interface names, status, byte and packet counters from the operating system in one cross-platform library.

**Q24. How is bandwidth calculated?**

A. NetWatch reads the interface byte counters twice. Rate in Mbps = (change in bytes x 8) / change in seconds / 1,000,000.

**Q25. How is packet loss calculated?**

A. NetWatch sends 3 pings per cycle and counts replies. Loss % = (sent - received) / sent x 100.

**Q26. How does the system detect internet failure?**

A. It pings a public host (default 1.1.1.1) and makes a small HTTPS request. If both fail, Internet is OFFLINE.

**Q27. How does the system detect gateway failure?**

A. It finds the default gateway from the routing table and pings it. If there is no reply, the gateway shows UNREACHABLE.

**Q28. What happens if DNS fails?**

A. The DNS card shows FAILED, an alert and event are created, and the overall status becomes DEGRADED. The Troubleshooter gives a possible cause and steps.

**Q29. What happens when a service is down?**

A. The TCP connection attempt fails, the service shows DOWN, an alert is raised, the event log shows SERVICE DOWN and the status becomes DEGRADED.

**Q30. What is HTTP status code 200?**

A. 200 means OK: the request succeeded.

**Q31. What is HTTP status code 500?**

A. 500 means Internal Server Error: the server had a problem. NetWatch marks such a URL as DOWN.

**Q32. What are the limitations?**

A. It checks only basic connectivity, cannot find every root cause, some routers block ping, bandwidth is only this computer's traffic, history is in memory only and it monitors only this computer and configured hosts.

**Q33. What is the future scope?**

A. SNMP monitoring, multi-device monitoring, a database for history, email/SMS alerts, role-based access, a central server, Docker deployment and Prometheus/Grafana integration.

**Q34. Why polling and not WebSockets?**

A. Polling every 2 to 5 seconds is simple, reliable and easy to understand. WebSockets would add complexity without much benefit here.

**Q35. Why do you use a background thread?**

A. Network checks can take seconds. A background thread does them so the web server stays responsive and always returns the latest stored results.

**Q36. How do you know the data is real?**

A. All values come from the OS and network: ping, sockets, DNS lookups, HTTP requests and psutil counters. If something cannot be measured, the dashboard shows Unavailable.

**Q37. What is the three-way handshake?**

A. SYN, SYN-ACK, ACK. It sets up a TCP connection. NetWatch's service check completes a TCP connection and then closes it.

**Q38. How does the TCP service check work?**

A. It makes one TCP connection attempt to the configured host and port with a timeout. Connected means UP; refused, timeout or error means DOWN.

**Q39. Is NetWatch a port scanner?**

A. No. It only checks the host and port combinations you configure, one attempt each. There is no scanning of ranges or devices.

**Q40. What is the OSI layer of ping, TCP and HTTP?**

A. Ping (ICMP) works at the network layer, TCP at the transport layer, and HTTP and DNS at the application layer.

**Q41. What is DHCP?**

A. DHCP gives devices an IP address, gateway and DNS server automatically when they join a network.

**Q42. What is NAT?**

A. NAT lets many private devices share one public IP address. Home routers use it.

**Q43. What is a private IP address?**

A. Private ranges are 10.0.0.0/8, 172.16.0.0/12 and 192.168.0.0/16. They are not routed on the public internet.

**Q44. What is a router?**

A. A router forwards packets between networks using IP addresses and routing tables.

**Q45. What is the difference between a switch and a router?**

A. A switch connects devices inside one network using MAC addresses. A router connects different networks using IP addresses.

**Q46. What is jitter?**

A. Jitter is the variation in latency from one packet to the next. NetWatch shows min and max latency, which gives a rough idea of it.

**Q47. What is a MAC address?**

A. A MAC address is the hardware address of a network adapter, for example AA-BB-CC-11-22-33.

**Q48. What is the difference between IPv4 and IPv6?**

A. IPv4 uses 32-bit addresses; IPv6 uses 128-bit addresses and gives a much larger address space.

**Q49. Why is the gateway sometimes UNREACHABLE when the internet works?**

A. Some routers do not reply to ping (ICMP). The internet still works, so this is a limitation of the check, not necessarily a fault.

**Q50. What does DEGRADED mean?**

A. At least one test is failing or latency/packet loss is above the threshold, but basic connectivity may still exist.

**Q51. What does OFFLINE mean?**

A. The internet is not reachable and the gateway is not reachable (or there is no local IP address): basic connectivity is unavailable.

**Q52. How are alerts generated?**

A. The engine compares real results with thresholds and states, for example latency above 200 ms, loss above 10%, gateway unreachable or a service DOWN.

**Q53. How do you limit memory?**

A. Events use a deque with a maximum of 100. Ping history keeps 200 samples and bandwidth history 450. Old items are removed automatically.

**Q54. How is input validated?**

A. Hostnames and IPs are checked by pattern, ports must be 1 to 65535, URLs must be http or https, thresholds must be in range, and the number of services is limited.

**Q55. How did you protect against command injection?**

A. The host is validated first and the ping command is run with an argument list, not through a shell.

**Q56. What happens if psutil is missing?**

A. The dashboard keeps running, shows an interface message and Unavailable for statistics, and the README tells the user to install psutil.

**Q57. What if one check crashes?**

A. Each check is wrapped in try/except. The error is logged as an event and the other checks continue.

**Q58. How does the Troubleshooter work?**

A. It runs six safe tests in order (interface, gateway, gateway ping, DNS, internet, services) and shows PASS/FAIL with a possible cause and suggestions.

**Q59. How can you demonstrate a changing network condition?**

A. Start the demo service, add it in Configuration, stop it to get SERVICE DOWN, start it again to get SERVICE RESTORED. You can also turn Wi-Fi off and on.

**Q60. Why is the server bound to 127.0.0.1?**

A. So only this computer can open the dashboard. The tool has no login, so it should not be exposed to others.

**Q61. What is the difference between monitoring and sniffing?**

A. Monitoring checks the health of connectivity and services. Sniffing captures other people's traffic. NetWatch does not sniff.

**Q62. What is a timeout and why is it needed?**

A. A timeout is the maximum waiting time for a reply. Without it a failed check could wait forever and freeze the monitor.
