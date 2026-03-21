package main

import "time"

// Event is an ordered UNO continuity event included in a block.
type Event struct {
	Type    string                 `json:"type"`
	Agent   string                 `json:"agent"`
	EventID string                 `json:"event_id"`
	Payload map[string]interface{} `json:"payload"`
}

// Block is the canonical chain unit finalized by quorum.
type Block struct {
	Round      uint64            `json:"round"`
	Timestamp  time.Time         `json:"timestamp"`
	Producer   string            `json:"producer"`
	Events     []Event           `json:"events"`
	ParentHash string            `json:"parent_hash"`
	BlockHash  string            `json:"block_hash"`
	Signatures map[string]string `json:"signatures"`
}
