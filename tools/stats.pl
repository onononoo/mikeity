#!/usr/bin/env perl
#
# stats.pl: numbers about the text of each part, read straight from the
# content files (not the built site).
#
#   perl tools/stats.pl            a table for every part
#   perl tools/stats.pl --words    also list the most used long words
#
# for each part it counts words, sections, links, and estimates how hard the
# text is to read with the flesch reading ease score (higher is easier; 60 to
# 70 is plain english, below 30 is very hard).

use strict;
use warnings;
use utf8;
use File::Basename qw(dirname basename);
use File::Spec;

binmode STDOUT, ':encoding(utf-8)';

my $show_words = grep { $_ eq '--words' } @ARGV;
my $root = File::Spec->rel2abs(File::Spec->catdir(dirname(__FILE__), '..'));
my $dir  = File::Spec->catdir($root, 'content', 'eras');

opendir(my $dh, $dir) or die "cannot open $dir: $!\n";
my @files = sort grep { /^\d\d-.*\.txt$/ } readdir($dh);
closedir($dh);
die "no content files found in $dir\n" unless @files;

# a rough syllable counter: count groups of vowels, with a few english fixes
sub syllables {
	my ($word) = @_;
	$word = lc $word;
	$word =~ s/[^a-z]//g;
	return 0 unless length $word;
	return 1 if length($word) <= 3;
	$word =~ s/(?:[^laeiouy]es|ed|[^laeiouy]e)$//;
	$word =~ s/^y//;
	my $n = () = $word =~ /[aeiouy]{1,2}/g;
	return $n || 1;
}

my (%total, %common);
my @rows;

for my $file (@files) {
	my $path = File::Spec->catfile($dir, $file);
	open(my $fh, '<:encoding(utf-8)', $path) or die "cannot read $path: $!\n";

	my %c = map { $_ => 0 } qw(words sentences syllables sections subsections terms people parts tables items);
	my $in_table = 0;

	while (my $line = <$fh>) {
		chomp $line;
		next if $line =~ /^#(?!#)/;    # writer's notes

		if ($line =~ /^===\s/)   { $c{subsections}++; next; }
		if ($line =~ /^==\s/)    { $c{sections}++;    next; }

		if ($line =~ /^\|/) {
			$c{tables}++ unless $in_table;
			$in_table = 1;
		} else {
			$in_table = 0;
		}
		$c{items}++ if $line =~ /^[-+] /;

		# count links, then turn them into their visible words
		$c{people} += () = $line =~ /\[\[@/g;
		$c{parts}  += () = $line =~ /\[\[part:/g;
		$c{terms}  += () = $line =~ /\[\[(?!@|part:)/g;
		$line =~ s/\[\[([^\]|]+)\|([^\]]+)\]\]/$2/g;
		$line =~ s/\[\[@?(?:part:)?([^\]]+)\]\]/$1/g;
		$line =~ s/\*\*//g;
		next if $line =~ /^\|/;    # table rows are not prose

		my @w = $line =~ /([a-z0-9'’-]+)/gi;
		$c{words} += @w;
		$c{syllables} += syllables($_) for @w;
		$c{sentences} += () = $line =~ /[.!?](?:\s|$)/g;
		for (@w) { $common{lc $_}++ if length($_) >= 9 && !/\d/ }
	}
	close $fh;

	$c{sentences} ||= 1;
	my $wps  = $c{words} / $c{sentences};
	my $spw  = $c{words} ? $c{syllables} / $c{words} : 0;
	my $ease = 206.835 - 1.015 * $wps - 84.6 * $spw;

	(my $name = basename($file, '.txt')) =~ s/^(\d\d)-//;
	push @rows, [$1 + 0, $name, @c{qw(words sections subsections terms people tables)}, sprintf('%.1f', $wps), sprintf('%.0f', $ease)];
	$total{$_} += $c{$_} for keys %c;
}

my @head = ('#', 'part', 'words', 'sect', 'subs', 'terms', 'people', 'tables', 'w/sent', 'ease');
my $fmt  = "%-3s %-24s %7s %5s %5s %6s %7s %7s %7s %5s\n";

printf $fmt, @head;
printf $fmt, map { '-' x length } @head;
printf $fmt, @$_ for @rows;
printf $fmt, map { '-' x length } @head;

my $wps  = $total{words} / ($total{sentences} || 1);
my $ease = 206.835 - 1.015 * $wps - 84.6 * ($total{syllables} / ($total{words} || 1));
printf $fmt, '', 'all parts', $total{words}, $total{sections}, $total{subsections},
	$total{terms}, $total{people}, $total{tables}, sprintf('%.1f', $wps), sprintf('%.0f', $ease);

print "\nlinks: $total{terms} to the glossary, $total{people} to people, $total{parts} to other parts.\n";
printf "reading time: about %d minutes at 230 words a minute.\n", $total{words} / 230 + 0.5;

if ($show_words) {
	my @top = (sort { $common{$b} <=> $common{$a} || $a cmp $b } keys %common)[0 .. 19];
	print "\nmost used long words:\n";
	printf "  %-20s %d\n", $_, $common{$_} for grep { defined } @top;
}
