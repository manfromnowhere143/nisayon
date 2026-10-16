// Native transport controls for vla.cpp PR #34. No model or robot execution.
// The included upstream functions and queue retain their upstream licenses.
#include <zmq.hpp>
#include "serving/request_queue.h"
#include <algorithm>
#include <cstdio>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include "routing_functions.inc"

using vla::serving::PushResult;
using vla::serving::QueueMode;
using vla::serving::RequestQueue;

static void require(bool ok, const char * message) {
    if (!ok) throw std::runtime_error(message);
}

static std::string hex(const std::string & bytes) {
    static const char * digits = "0123456789abcdef";
    std::string out;
    for (unsigned char c : bytes) {
        out.push_back(digits[c >> 4]);
        out.push_back(digits[c & 15]);
    }
    return out;
}

static std::vector<std::string> bytes_of(const std::vector<zmq::message_t> & frames) {
    std::vector<std::string> bytes;
    for (const auto & f : frames)
        bytes.emplace_back(static_cast<const char *>(f.data()), f.size());
    return bytes;
}

static void print_frames(const std::vector<std::string> & frames) {
    std::cout << '[';
    for (size_t i = 0; i < frames.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << '"' << hex(frames[i]) << '"';
    }
    std::cout << ']';
}

struct Job {
    std::vector<zmq::message_t> envelope;
    std::string key;
    int rid = 0;
};

struct Case {
    const char * name;
    QueueMode mode;
    bool reverse = false;
    bool ascii = false;
    bool same_client = false;
};

static const char * result_name(PushResult r) {
    switch (r) {
        case PushResult::QUEUED: return "queued";
        case PushResult::REPLACED: return "replaced";
        case PushResult::REJECTED: return "rejected";
    }
    throw std::runtime_error("unknown queue result");
}

static bool transport_case(const Case & c) {
    zmq::context_t context(1);
    zmq::socket_t router(context, zmq::socket_type::router);
    zmq::socket_t dealer(context, zmq::socket_type::dealer);
    zmq::socket_t req(context, zmq::socket_type::req);
    for (auto * socket : {&router, &dealer, &req}) {
        socket->set(zmq::sockopt::linger, 0);
        socket->set(zmq::sockopt::rcvtimeo, 2000);
        socket->set(zmq::sockopt::sndtimeo, 2000);
    }
    const std::string dealer_id = c.ascii ? "client-a" : std::string("robot\0", 6);
    const std::string req_id = c.ascii ? "client-b" : "robot";
    dealer.set(zmq::sockopt::routing_id, dealer_id);
    req.set(zmq::sockopt::routing_id, req_id);
    router.bind("inproc://routing-control");
    dealer.connect("inproc://routing-control");
    req.connect("inproc://routing-control");
    zmq::socket_t * peers[] = {&dealer, &req};
    const std::vector<std::string> expected_envelopes[] = {{dealer_id}, {req_id, ""}};
    RequestQueue<Job> queue(c.mode);
    std::map<int, std::vector<std::string>> original_envelopes;
    std::map<int, std::string> sent;
    std::map<int, std::string> expected;
    std::vector<int> submissions[2];
    std::vector<int> popped;
    bool passed = true;

    auto respond = [&](Job & job, const std::string & status) {
        require(bytes_of(job.envelope) == original_envelopes.at(job.rid),
                "queue changed the original response envelope");
        require(sent.emplace(job.rid, status).second, "duplicate server response");
        require(send_multipart(router, job.envelope,
                               std::to_string(job.rid) + ":" + status), "send failed");
    };

    std::cout << "{\"name\":\"" << c.name << "\",\"pushes\":[";
    for (int rid = 1; rid <= 2; ++rid) {
        int peer = c.same_client ? 0 : (c.reverse ? 2 - rid : rid - 1);
        submissions[peer].push_back(rid);
        expected[rid] = c.same_client && rid == 1 ? "superseded" : "served";
        require(peers[peer]->send(zmq::buffer(std::to_string(rid)), zmq::send_flags::none)
                    .has_value(), "client send timed out");
        std::vector<zmq::message_t> frames;
        require(recv_multipart(router, frames), "router receive timed out");
        require(!frames.empty(), "router received no frames");
        const auto body = std::string(static_cast<const char *>(frames.back().data()),
                                      frames.back().size());
        require(body == std::to_string(rid), "request payload changed");
        frames.pop_back();
        auto envelope = bytes_of(frames);
        require(envelope == expected_envelopes[peer], "unexpected native envelope");
        original_envelopes.emplace(rid, envelope);
        auto key = envelope_key(frames);
        Job job{std::move(frames), key, rid};
        std::optional<Job> displaced;
        auto status = queue.push(std::move(job),
            [](const Job & j) -> const std::string & { return j.key; }, displaced);
        if (rid > 1) std::cout << ',';
        std::cout << "{\"rid\":" << rid << ",\"peer\":" << peer
                  << ",\"envelope_hex\":";
        print_frames(envelope);
        std::cout << ",\"key_hex\":\"" << hex(key) << "\",\"result\":\""
                  << result_name(status) << "\",\"depth\":" << queue.size()
                  << ",\"displaced_rid\":" << (displaced ? displaced->rid : 0) << '}';
        const bool should_replace = c.same_client && rid == 2;
        passed &= status == (should_replace ? PushResult::REPLACED : PushResult::QUEUED);
        passed &= queue.size() == static_cast<size_t>(c.same_client ? 1 : rid);
        passed &= (displaced ? displaced->rid : 0) == (should_replace ? 1 : 0);
        if (displaced) respond(*displaced, status == PushResult::REPLACED ?
                                         "superseded" : "rejected");
    }
    queue.stop();
    Job job;
    while (queue.pop(job)) {
        popped.push_back(job.rid);
        respond(job, "served");
    }
    const std::vector<int> expected_order = c.same_client ? std::vector<int>{2} :
                                                           std::vector<int>{1, 2};
    passed &= popped == expected_order;
    std::cout << "],\"pop_order\":[";
    for (size_t i = 0; i < popped.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << popped[i];
    }
    std::cout << "],\"receipts\":[";
    bool first_receipt = true;
    for (int peer = 0; peer < 2; ++peer) {
        for (int rid : submissions[peer]) {
            std::vector<zmq::message_t> receipt;
            require(recv_multipart(*peers[peer], receipt), "client receive timed out");
            require(receipt.size() == 1, "unexpected client response frames");
            const auto body = std::string(static_cast<const char *>(receipt[0].data()),
                                          receipt[0].size());
            require(body == std::to_string(rid) + ":" + sent.at(rid),
                    "response arrived at the wrong client or in the wrong order");
            passed &= sent.at(rid) == expected.at(rid);
            if (!first_receipt) std::cout << ',';
            first_receipt = false;
            std::cout << "{\"peer\":" << peer << ",\"rid\":" << rid
                      << ",\"status\":\"" << sent.at(rid) << "\"}";
        }
    }
    require(sent.size() == 2, "response count changed");
    passed &= queue.size() == 0;
    std::cout << "],\"passed\":" << (passed ? "true" : "false") << '}';
    return passed;
}

static bool finite_injectivity() {
    const std::string alphabet("\0:a", 3);
    std::vector<std::string> pool{std::string()};
    for (char a : alphabet) pool.push_back(std::string(1, a));
    for (char a : alphabet)
        for (char b : alphabet) pool.push_back(std::string{a, b});
    std::vector<std::vector<std::string>> envelopes;
    for (const auto & first : pool) {
        if (first.empty() || first[0] == '\0') continue;
        envelopes.push_back({first});
        for (const auto & second : pool) {
            envelopes.push_back({first, second});
            for (const auto & third : pool) envelopes.push_back({first, second, third});
        }
    }
    require(envelopes.size() == 1464, "finite pool size changed");
    const std::set<std::vector<std::string>> independent_vectors(envelopes.begin(),
                                                               envelopes.end());
    require(independent_vectors.size() == envelopes.size(), "duplicate finite input");
    std::map<std::string, std::vector<std::string>> seen;
    size_t collisions = 0;
    std::cout << "{\"inputs\":" << envelopes.size() << ",\"first_collision\":";
    for (const auto & envelope : envelopes) {
        std::vector<zmq::message_t> frames;
        for (const auto & bytes : envelope) frames.emplace_back(bytes.data(), bytes.size());
        const auto key = envelope_key(frames);
        auto inserted = seen.emplace(key, envelope);
        if (!inserted.second) {
            require(inserted.first->second != envelope, "identical vector counted as collision");
            if (collisions++ == 0) {
                std::cout << "{\"first_hex\":";
                print_frames(inserted.first->second);
                std::cout << ",\"second_hex\":";
                print_frames(envelope);
                std::cout << ",\"key_hex\":\"" << hex(key) << "\"}";
            }
        }
    }
    if (!collisions) std::cout << "null";
    std::cout << ",\"unique_keys\":" << seen.size()
              << ",\"additional_inputs_colliding\":" << collisions
              << ",\"passed\":" << (collisions == 0 ? "true" : "false") << '}';
    return collisions == 0;
}

int main() {
    try {
        const Case cases[] = {
            {"latest_dealer_then_req", QueueMode::LATEST},
            {"latest_req_then_dealer", QueueMode::LATEST, true},
            {"latest_ascii_distinct", QueueMode::LATEST, false, true},
            {"latest_same_binary_client", QueueMode::LATEST, false, false, true},
            {"fifo_binary_distinct", QueueMode::FIFO},
        };
        int passed = 0;
        std::cout << "{\"transport_cases\":[";
        for (size_t i = 0; i < 5; ++i) {
            if (i) std::cout << ',';
            passed += transport_case(cases[i]);
        }
        std::cout << "],\"transport_passed\":" << passed << ",\"finite_injectivity\":";
        const bool injective = finite_injectivity();
        std::cout << "}\n";
        return passed == 5 && injective ? 0 : 1;
    } catch (const std::exception & e) {
        std::cerr << "routing harness error: " << e.what() << '\n';
        return 2;
    }
}
