package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/google/uuid"
)

func main() {
	port := flag.Int("port", 9000, "libp2p listen port")
	flag.Parse()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	nodeID := "uno:agent:" + uuid.NewString()
	listen := fmt.Sprintf("/ip4/0.0.0.0/tcp/%d", *port)
	n, err := NewNode(ctx, listen, "uno-vrf-seed")
	if err != nil {
		log.Fatalf("node init failed: %v", err)
	}
	defer n.Host.Close()

	log.Printf("node id: %s", nodeID)
	for _, addr := range n.Host.Addrs() {
		log.Printf("listening on %s/p2p/%s", addr, n.Host.ID())
	}
	log.Println("node ready")

	time.Sleep(2 * time.Second)
	if err := n.StartDiscovery(); err != nil {
		log.Fatalf("mdns init failed: %v", err)
	}
	log.Println("mdns discovery enabled")

	ticker := time.NewTicker(4 * time.Second)
	defer ticker.Stop()

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	for {
		select {
		case <-ctx.Done():
			return
		case <-sig:
			log.Println("shutting down")
			return
		case <-ticker.C:
			log.Printf("connected peers: %d", len(n.Host.Network().Peers()))
		}
	}
}
