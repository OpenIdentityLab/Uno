package main

import (
	"context"
	"fmt"
	"log"
	"sync"

	libp2p "github.com/libp2p/go-libp2p"
	pubsub "github.com/libp2p/go-libp2p-pubsub"
	host "github.com/libp2p/go-libp2p/core/host"
	peer "github.com/libp2p/go-libp2p/core/peer"
	mdns "github.com/libp2p/go-libp2p/p2p/discovery/mdns"
	noise "github.com/libp2p/go-libp2p/p2p/security/noise"
)

const discoveryTag = "uno-layer1-mdns"

// Node holds p2p, consensus and VRF state.
type Node struct {
	Host         host.Host
	PubSub       *pubsub.PubSub
	CurrentRound *RoundState
	HotStuff     *HotStuffLite
	VRFSeed      string

	BlocksTopic    *pubsub.Topic
	ProposalsTopic *pubsub.Topic
	VotesTopic     *pubsub.Topic
	RevokesTopic   *pubsub.Topic

	mu sync.RWMutex
}

func NewNode(ctx context.Context, listenAddr string, vrfSeed string) (*Node, error) {
	h, err := libp2p.New(
		libp2p.ListenAddrStrings(listenAddr),
		libp2p.Security(noise.ID, noise.New),
	)
	if err != nil {
		return nil, fmt.Errorf("create host: %w", err)
	}

	ps, err := pubsub.NewGossipSub(ctx, h)
	if err != nil {
		return nil, fmt.Errorf("create gossipsub: %w", err)
	}

	blocks, err := ps.Join("/uno/blocks")
	if err != nil {
		return nil, err
	}
	proposals, err := ps.Join("/uno/proposals")
	if err != nil {
		return nil, err
	}
	votes, err := ps.Join("/uno/votes")
	if err != nil {
		return nil, err
	}
	revocations, err := ps.Join("/uno/revocations")
	if err != nil {
		return nil, err
	}

	n := &Node{
		Host:           h,
		PubSub:         ps,
		HotStuff:       NewHotStuffLite(),
		VRFSeed:        vrfSeed,
		BlocksTopic:    blocks,
		ProposalsTopic: proposals,
		VotesTopic:     votes,
		RevokesTopic:   revocations,
	}

	if err := setupMDNS(ctx, h); err != nil {
		return nil, err
	}
	return n, nil
}

type discoveryNotifee struct {
	h host.Host
}

func (n *discoveryNotifee) HandlePeerFound(pi peer.AddrInfo) {
	if pi.ID == n.h.ID() {
		return
	}
	if err := n.h.Connect(context.Background(), pi); err != nil {
		log.Printf("mdns connect failed to %s: %v", pi.ID.String(), err)
		return
	}
	log.Printf("mdns peer discovered: %s", pi.ID.String())
}

func setupMDNS(ctx context.Context, h host.Host) error {
	s := mdns.NewMdnsService(h, discoveryTag, &discoveryNotifee{h: h})
	return s.Start()
}
