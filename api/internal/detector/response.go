package detector

import "fmt"

const coordinateCount = 4

type wireBox struct {
	BBox      []int    `json:"bbox"`
	IsChecked *bool    `json:"is_checked"`
	FillRatio *float64 `json:"fill_ratio"`
}

type wireTimings struct {
	Decode   *float64 `json:"decode"`
	Detect   *float64 `json:"detect"`
	Classify *float64 `json:"classify"`
}

func decodeResult(data []byte) (Result, error) {
	var body struct {
		Image   *Dimensions  `json:"image"`
		Boxes   *[]wireBox   `json:"boxes"`
		Timings *wireTimings `json:"timings_ms"`
	}
	if err := decodeStrict(data, &body); err != nil {
		return Result{}, err
	}
	if body.Image == nil ||
		body.Image.Width <= 0 ||
		body.Image.Height <= 0 ||
		body.Boxes == nil ||
		body.Timings == nil {
		return Result{}, fmt.Errorf("missing image, boxes or timings")
	}
	timing := body.Timings
	if timing.Decode == nil ||
		timing.Detect == nil ||
		timing.Classify == nil ||
		*timing.Decode < 0 ||
		*timing.Detect < 0 ||
		*timing.Classify < 0 {
		return Result{}, fmt.Errorf("invalid processing timings")
	}
	result := Result{
		Image: *body.Image,
		Boxes: make([]Box, 0, len(*body.Boxes)),
		Timings: Timings{
			Decode:   *timing.Decode,
			Detect:   *timing.Detect,
			Classify: *timing.Classify,
		},
	}
	for _, box := range *body.Boxes {
		if len(box.BBox) != coordinateCount ||
			box.IsChecked == nil ||
			box.FillRatio == nil ||
			*box.FillRatio < 0 ||
			*box.FillRatio > 1 {
			return Result{}, fmt.Errorf("invalid checkbox fields")
		}
		bounds := [coordinateCount]int(box.BBox)
		if bounds[0] < 0 ||
			bounds[1] < 0 ||
			bounds[0] >= bounds[2] ||
			bounds[1] >= bounds[3] ||
			bounds[2] > body.Image.Width ||
			bounds[3] > body.Image.Height {
			return Result{}, fmt.Errorf("checkbox lies outside image bounds")
		}
		result.Boxes = append(result.Boxes, Box{
			BBox:      bounds,
			IsChecked: *box.IsChecked,
			FillRatio: *box.FillRatio,
		})
	}
	return result, nil
}
