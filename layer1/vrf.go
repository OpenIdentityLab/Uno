package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"io"
	"strings"

	"golang.org/x/crypto/hkdf"
)

// ComputeVRF derives a pseudorandom output and a proof from seed + nodeID.
func ComputeVRF(seed, nodeID string) (string, string, error) {
	info := []byte("uno-vrf:" + nodeID)
	r := hkdf.New(sha256.New, []byte(seed), []byte(nodeID), info)
	out := make([]byte, 32)
	if _, err := io.ReadFull(r, out); err != nil {
		return "", "", err
	}

	mac := hmac.New(sha256.New, []byte(nodeID))
	mac.Write(out)
	proof := mac.Sum(nil)
	return hex.EncodeToString(out), hex.EncodeToString(proof), nil
}

// VerifyVRF checks that proof matches output under nodePubKey.
func VerifyVRF(output, proof, nodePubKey string) bool {
	out, err := hex.DecodeString(strings.TrimPrefix(output, "0x"))
	if err != nil {
		return false
	}
	gotProof, err := hex.DecodeString(strings.TrimPrefix(proof, "0x"))
	if err != nil {
		return false
	}

	mac := hmac.New(sha256.New, []byte(nodePubKey))
	mac.Write(out)
	expected := mac.Sum(nil)
	return hmac.Equal(expected, gotProof)
}
