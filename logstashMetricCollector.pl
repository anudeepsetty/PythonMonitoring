#!/usr/bin/perl


# --- Configuration ---
$log_window     = "5 minutes ago";
$queue_path     = "/mnt/data/logstash/queue/";
$api_url        = "http://localhost:9600/_node/stats/pipelines";
$user           = "metricCollector";
$password       = "<password>";
$index_name     = "apitrans_logstash_metrics";
$Monitorhost    = "<Destination ELK URL>";
$cluster        = "Non-Prod";
$location       = "LasVegas";
$sys_timestamp  = `date -u "+%Y-%m-%dT%H:%M:%SZ"`;
chomp $sys_timestamp;

print $sys_timestamp, "\n";

my %disk_usage;
my @du_lines = `du -h --max-depth=1 $queue_path 2>/dev/null`;

foreach my $line (@du_lines) {
    chomp($line);
    # Regex captures: [Size][Unit] [Path]
    if ($line =~ /^([0-9.]+)([KMG]?)\t.*\/([^\/]+)$/) {
        my ($val, $unit, $pipeline_id) = ($1, $2, $3);
        my $converted_val;

        if ($unit eq 'G') {
            # GB to MB
            $converted_val = $val * 1024;
        } elsif ($unit eq 'K') {
            # KB to MB
            $converted_val = $val / 1024;
        } elsif ($unit eq 'M') {
            # Already MB
            $converted_val = $val;
        } else {
            # Bytes or unknown (assumed small, treat as 0MB)
            $converted_val = 0;
        }

        # Store formatted as "123.4MB"
        $disk_usage{$pipeline_id} = sprintf("%.2f", $converted_val);
    }
}

# FIX: We use \@tsv to prevent Perl from looking for an array named @tsv
my $cmd = qq(curl -s -XGET '$api_url' | jq -r '.host as \$hostname | .pipelines | to_entries[] | [\$hostname, .key, .value.events.in // 0, .value.events.out // 0, .value.queue.events_count // 0, (.value.pipeline.workers // "0"), (.value.pipeline.batch_size // "0"), (.value.pipeline.batch_delay // "0"), (.value.reloads.successes // 0), (.value.reloads.failures // 0)] | \@tsv');

print $cmd;

my @lines = `$cmd`;

# Header
print sprintf("%-25s | %-35s | %-10s | %-10s | %-8s | %-6s | %-6s | %-6s| %-6s\n",
    "Host", "Pipeline", "Events In", "Events Out", "Queue", "Errors", "Rel_S", "Rel_f", "Disk_BackQueue");
print "-" x 130 . "\n";

foreach my $line (@lines) {
    chomp($line);
    my ($host, $id, $in, $out, $q_count, $workers, $b_size, $b_delay, $rel_s, $rel_f) = split("\t", $line);

    # Error count for specific pipeline
    my $error_regex = "\\[$id\\].*could not index";
    my $error_count = `journalctl -u logstash --since "$log_window" | grep -Eic "$error_regex" 2>/dev/null`;
    chomp($error_count);
    $error_count ||= 0;

    #my $reloads = "$rel_s/$rel_f";

    my $disk_size = $disk_usage{$id} // "0.00";

    print sprintf("%-20s | %-35s | %-10s | %-10s | %-8s | %-6s | %-6s| %-6s| %-6s\n",
        $host, $id, $in, $out, $q_count, $error_count, $rel_s, $rel_f, $disk_size);

    $action_line    = "{\"create\":{\"_index\":\"$index_name\"}}\n";
    $doc_line       = "{\"cluster\":\"$cluster\",\"location\":\"$location\",\"host_name\":\"$host\",\"pipeline\":\"$id\",\"event_in\":\"$in\",\"event_out\":\"$out\",\"backlog\":\"$q_count\",\"error_count\":\"$error_count\",\"reload_success\":\"$rel_s\",\"reload_failure\":\"$rel_f\",\"\@timestamp\":\"$sys_timestamp\",\"backlog_disksize\":\"$disk_size\"}\n";

    $ndjson_payload .= $action_line;
    $ndjson_payload .= $doc_line;

}


print $ndjson_payload;

$temp_file = "bulk_data.json";

print $ndjson_payload,"\n";

open ($fh, '>', $temp_file) or die $!;
print $fh $ndjson_payload . "\n";
close($fh);

@post_curl = `curl -k -u $user:$password -H 'Content-Type: application/x-ndjson' -XPOST 'https://$Monitorhost:9243/_bulk?pretty' --data-binary \@$temp_file`;

print @post_curl;

unlink($temp_file);
